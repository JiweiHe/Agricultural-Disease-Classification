# -*- coding: utf-8 -*-
"""
Created on Mon Oct 22 10:01:41 2018

@author: 16703
"""
import os
from keras.applications.densenet import DenseNet121
#from keras.applications.resnet50 import ResNet50
from keras.applications.xception import Xception
from keras.layers import Input,Dense,GlobalMaxPooling2D,Dropout
from keras.models import Model
import keras
import util
import random
import config
import numpy as np
from sklearn.utils import shuffle
import cv2
import json
from keras.utils import np_utils
from keras.callbacks import ModelCheckpoint
from keras.callbacks import ReduceLROnPlateau
def Multimodel(cnn_weights_path=None,all_weights_path=None,class_num=61,cnn_no_vary=False):
	'''
	获取densent121,xinception并联的网络
	此处的cnn_weights_path是个列表是densenet和xception的卷积部分的权值
	'''
	input_layer=Input(shape=(229,229,3))
	
	dense=DenseNet121(include_top=False,weights=None,input_tensor=input_layer,
		input_shape=(229,229,3))
	xception=Xception(include_top=False,weights=None,input_tensor=input_layer,
		input_shape=(250,250,3))
	#res=ResNet50(include_top=False,weights=None,input_shape=(229,229,3))
 
	if cnn_no_vary:
		for i,layer in  enumerate(dense.layers):
			dense.layers[i].trainable=True
		for i,layer in enumerate(xception.layers):
			xception.layers[i].trainable=False
		#for i,layer in enumerate(res.layers):
		#	res.layers[i].trainable=False
	if cnn_weights_path!=None:
		dense.load_weights(cnn_weights_path[0])
		xception.load_weights(cnn_weights_path[1])
 
	#print(dense.shape,xception.shape)
	#对dense_121和xception进行全局最大池化
	top1_model=GlobalMaxPooling2D(input_shape=(7,7,1024),data_format='channels_last')(dense.output)
	top2_model=GlobalMaxPooling2D(input_shape=(7,7,1024),data_format='channels_last')(xception.output)
	#top3_model=GlobalMaxPool2D(input_shape=res.output_shape)(res.outputs[0])
	
	#print(top1_model.shape,top2_model.shape)
	#把top1_model和top2_model连接起来
	t=keras.layers.Concatenate(axis=1)([top1_model,top2_model])
	#第一个全连接层
	top_model=Dense(units=1024,activation="relu")(t)
	top_model=Dropout(rate=0.5)(top_model)
	top_model=Dense(units=class_num,activation="softmax")(top_model)
	
	model=Model(inputs=input_layer,outputs=top_model)
 
	#加载全部的参数
	if all_weights_path:
		model.load_weights(all_weights_path)
	return model
weight_path=['./densenet121_weights_tf_dim_ordering_tf_kernels_notop.h5','./xception_weights_tf_dim_ordering_tf_kernels_notop.h5 ']
Adam=keras.optimizers.Adam(lr=0.0001)
model=Multimodel(cnn_weights_path=weight_path,all_weights_path=None,class_num=59,cnn_no_vary=True)
learning_rate_reduction = ReduceLROnPlateau(monitor='val_acc', patience=1, verbose=1, factor=0.1, min_lr=0.0000001)
model.compile(optimizer=Adam, loss='categorical_crossentropy',metrics=['accuracy'])
def rotate(image, angle=15, scale=0.9):
    w = image.shape[1]
    h = image.shape[0]
    #rotate matrix
    M = cv2.getRotationMatrix2D((w/2,h/2), angle, scale)
    #rotate
    image = cv2.warpAffine(image,M,(w,h))
    return image

def custom_blur_demo(image):
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], np.float32) #锐化
    dst = cv2.filter2D(image, -1, kernel=kernel)
    return dst

def relight(imgsrc, alpha=1, bias=0):
    imgsrc = imgsrc.astype(float)
    imgsrc = imgsrc * alpha + bias
    imgsrc[imgsrc < 0] = 0
    imgsrc[imgsrc > 255] = 255
    imgsrc = imgsrc.astype(np.uint8)
    return imgsrc
#加载数据集
def load_feature(img_path):
    img = util.cv_imread(img_path)
    img= relight(img,random.uniform(0.9, 1.1), random.randint(-10, 10))
    crop= img / 255.
    crop = crop - 0.5
    crop = crop * 2.

    crop = cv2.resize(crop, (229, 229))
    return crop

def process_test(anno_file,dir):
    with open(anno_file) as file:
        annotations = json.load(file)
        img_paths = []
        labels = []
        for anno in annotations:
            if anno["disease_class"]==44 or anno["disease_class"]==45:
                continue
            img_paths.append(dir + anno["image_id"])
            if anno["disease_class"]>45:
                anno["disease_class"]=anno["disease_class"]-2
            labels.append(anno["disease_class"])
    return img_paths, labels

def data_generator(img_paths,labels,batch_size,is_shuffle=True):
    if is_shuffle:
        img_paths,labels = shuffle(img_paths,labels)
    num_sample = len(img_paths)
    print(num_sample)
    while True:
        if is_shuffle:
            img_paths, labels = shuffle(img_paths, labels)
       
        for offset in range(0,num_sample,batch_size):
            batch_paths = img_paths[offset:offset+batch_size]
            batch_labels = labels[offset:offset+batch_size]
            batch_labels=np.array(batch_labels)
            batch_labels=np_utils.to_categorical(batch_labels,num_classes=59)
            batch_features = [load_feature(path) for path in batch_paths]
           
            batch_feature = np.array(batch_features)
            yield batch_feature, batch_labels
            
batch_size=20
trian_img_paths,train_labels = process_test(config.TRAIN_ANNOTATION_FILE,config.TRAIN_DIR)

trian_img_paths1,train_labels1 = process_test(config.VAL_ANNOTATION_FILE,config.VAL_DIR)

model.load_weights('weights1.hdf5')
checkpoint = ModelCheckpoint('weights1.hdf5', monitor='val_acc', verbose=2, save_best_only=True, mode='max', period=1)

#训练模型
model.fit_generator(data_generator(trian_img_paths,train_labels,batch_size),samples_per_epoch=len(train_labels)//20,nb_epoch=3,validation_data=data_generator(trian_img_paths1,train_labels1,batch_size),nb_val_samples=4982//32,callbacks=[checkpoint,learning_rate_reduction])

model.save(os.path.join('./', 'my_model_multiplemodel.h5'))
