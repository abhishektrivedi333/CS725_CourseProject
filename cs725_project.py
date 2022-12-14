# -*- coding: utf-8 -*-
"""CS725_project.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Ylu7oVnPa8IdosLvrpoCFzAZogZAegaQ

# Project CS 725
A UNet based semantic segmentation based code to detect clouds taken from the satellite image. 
Three cases have been made in this notebook to check the effect of changing the hyperparameters of UNet architecture that is no. of down/up sampling blocks, initial feature map size, no. of convolutions performed in each down/up sampling block.

Important remarks:
- The train set will be splitted into train and validation sets.
- The dataset creation is discussed in: https://medium.com/@cordmaur/how-to-create-a-custom-dataset-loader-in-pytorch-from-scratch-for-multi-band-satellite-images-c5924e908edf
- The training phase with 25 epochs takes around 4:00 hrs.
"""

import numpy as np 
import pandas as pd
from pathlib import Path
from torch.utils.data import Dataset, DataLoader, sampler
from PIL import Image
import torch
import matplotlib.pyplot as plt
import time

"""## Creating the dataset"""

class Cloud_Data(Dataset):
    def __init__(self, r_dir, g_dir, b_dir, nir_dir, gt_dir, pytorch=True):
        super().__init__()
        
        # Loop through the files in red folder and combine, into a dictionary, the other bands
        self.files = [self.combine_all(f, g_dir, b_dir, nir_dir, gt_dir) for f in r_dir.iterdir() if not f.is_dir()]
        self.pytorch = pytorch
        
    def combine_all(self, r_file: Path, g_dir, b_dir,nir_dir, gt_dir):
        
        files = {'red': r_file, 
                 'green':g_dir/r_file.name.replace('red', 'green'),
                 'blue': b_dir/r_file.name.replace('red', 'blue'), 
                 'nir': nir_dir/r_file.name.replace('red', 'nir'),
                 'gt': gt_dir/r_file.name.replace('red', 'gt')}

        return files
                                       
    def __len__(self):
        
        return len(self.files)
     
    def open_image(self, idx, invert=False, include_nir=False):

        raw_rgb = np.stack([np.array(Image.open(self.files[idx]['red'])),
                            np.array(Image.open(self.files[idx]['green'])),
                            np.array(Image.open(self.files[idx]['blue'])),
                           ], axis=2)
    
        if include_nir:
            nir = np.expand_dims(np.array(Image.open(self.files[idx]['nir'])), 2)
            raw_rgb = np.concatenate([raw_rgb, nir], axis=2)
    
        if invert:
            raw_rgb = raw_rgb.transpose((2,0,1))
    
        # normalize
        return (raw_rgb / np.iinfo(raw_rgb.dtype).max)
    
    def open_as_array(self, idx, invert=False, include_nir=False):

        raw_rgb = np.stack([np.array(Image.open(self.files[idx]['red'])),
                            np.array(Image.open(self.files[idx]['green'])),
                            np.array(Image.open(self.files[idx]['blue'])),
                           ], axis=2)
    
        if include_nir:
            nir = np.expand_dims(np.array(Image.open(self.files[idx]['nir'])), 2)
            raw_rgb = np.concatenate([raw_rgb, nir], axis=2)
    
        if invert:
            raw_rgb = raw_rgb.transpose((2,0,1))
    
        # normalize
        return (raw_rgb / np.iinfo(raw_rgb.dtype).max)

    def open_mask(self, idx, add_dims=False):
        
        raw_mask = np.array(Image.open(self.files[idx]['gt']))
        raw_mask = np.where(raw_mask==255, 1, 0)
        
        return np.expand_dims(raw_mask, 0) if add_dims else raw_mask
    
    def __getitem__(self, idx):
        
        x = torch.tensor(self.open_image(idx, invert=self.pytorch, include_nir=True), dtype=torch.float32)
        y = torch.tensor(self.open_mask(idx, add_dims=False), dtype=torch.torch.int64)
        
        return x, y
    
    def open_as_pil(self, idx):
        
        arr = 256*self.open_image(idx)
        
        return Image.fromarray(arr.astype(np.uint8), 'RGB')
    
    def __repr__(self):
        s = 'Dataset class with {} files'.format(self.__len__())

        return s

_path = Path('../input/38cloud-cloud-segmentation-in-satellite-images/38-Cloud_training')
data = Cloud_Data(_path/'train_red', 
                    _path/'train_green', 
                    _path/'train_blue', 
                    _path/'train_nir',
                    _path/'train_gt')
len(data)

x1 = [];y1 = []
for i in range(1000):
    x, y = data[i]
    x1.append(x.numpy())
    y1.append(y.numpy())

x1 = np.array(x1)
y = np.array(y1)
x = np.moveaxis(x1, 1, -1)

"""# **Case 1. Single convolution in each up-sampling and down-sampling blocks. 5 block layers, initial feature map = 16.**"""

import tensorflow as tf
from tensorflow import keras
def down_block(x, filters, kernel_size=(3, 3), padding="same", strides=1):
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(x)
    p = keras.layers.MaxPool2D((2, 2), (2, 2))(c)
    return c, p

def up_block(x, skip, filters, kernel_size=(3, 3), padding="same", strides=1):
    us = keras.layers.UpSampling2D((2, 2))(x)
    concat = keras.layers.Concatenate()([us, skip])
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(concat)
    return c

def bottleneck(x, filters, kernel_size=(3, 3), padding="same", strides=1):
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(x)
    return c

image_size = 384
def UNet():
    f = [16, 32, 64, 128, 256, 512]
    inputs = keras.layers.Input((image_size, image_size, 4))
    
    p0 = inputs
    c1, p1 = down_block(p0, f[0]) #128 -> 64
    c2, p2 = down_block(p1, f[1]) #64 -> 32
    c3, p3 = down_block(p2, f[2]) #32 -> 16
    c4, p4 = down_block(p3, f[3]) #16 -> 8
    c5, p5 = down_block(p4, f[4]) #8 -> 4
    
    bn = bottleneck(p5, f[5])
    
    u1 = up_block(bn, c5, f[4]) #4 -> 8
    u2 = up_block(u1, c4, f[3]) #8 -> 16
    u3 = up_block(u2, c3, f[2]) #16 -> 32
    u4 = up_block(u3, c2, f[1]) #32 -> 64
    u5 = up_block(u4, c1, f[0]) #64 -> 128
    
    outputs = keras.layers.Conv2D(1, (1, 1), padding="same", activation="sigmoid")(u5)
    model = keras.models.Model(inputs, outputs)
    return model

model = UNet()
opt = keras.optimizers.Adam()
model.compile(optimizer=opt, loss="binary_crossentropy", metrics=["acc"])
model.summary()

# training the model and storing the accuracy and training loss after each epoch in hist variable.
hist = model.fit(x, y, validation_split = 0.2, batch_size=32,epochs=25)

plt.figure(figsize=(15,7))
plt.rcParams['font.size'] = '20'
plt.plot(hist.history['acc'])
plt.plot(hist.history['val_acc'])
plt.title('model accuracy')
plt.ylabel('accuracy')
plt.xlabel('epoch')
plt.grid()
plt.legend(['train', 'test'], loc='upper left')
plt.show()
# summarize history for loss
plt.figure(figsize=(15,7))
plt.plot(hist.history['loss'])
plt.rcParams['font.size'] = '20'
plt.plot(hist.history['val_loss'])
plt.title('model loss')
plt.ylabel('loss')
plt.grid()
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
plt.show()

x1 = [];y1 = []
for i in range(1000,1200):
    x, y = data[i]
    x1.append(x.numpy())
    y1.append(y.numpy())

x1 = np.array(x1)
y1 = np.array(y1)
x_test = np.moveaxis(x1, 1, -1)
y_test = y1

import cv2
for i in range(result.shape[0]):
  temp = cv2.threshold(result[i], 0.5, 1, cv2.THRESH_BINARY)[1]
  result[i] = np.expand_dims(temp,axis = 2)

r = 151
fig = plt.figure(figsize = (20,15))
fig.subplots_adjust(hspace=0.4, wspace=0.4)
ax = fig.add_subplot(1, 3, 1)
ax.imshow(x_test[r,:,:,:3])
plt.title('Test Image')
ax = fig.add_subplot(1, 3, 2)
ax.imshow(np.reshape(y_test[r], (384, 384)), cmap="gray")
plt.title('Binary Mask')
ax = fig.add_subplot(1, 3, 3)
ax.imshow(np.reshape(result[r], (384, 384)), cmap="gray")
plt.title('Predicted Mask')

bce = tf.keras.losses.BinaryCrossentropy(reduction='sum_over_batch_size')
bce(y_test, np.reshape(result, (200,384, 384))).numpy()

"""# **Case 2. Double convolution in each up-sampling and down-sampling blocks. 5 layer blocks, initial feature map = 16.**"""

import tensorflow as tf
from tensorflow import keras
def down_block(x, filters, kernel_size=(3, 3), padding="same", strides=1):
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(x)
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(c)
    p = keras.layers.MaxPool2D((2, 2), (2, 2))(c)
    return c, p

def up_block(x, skip, filters, kernel_size=(3, 3), padding="same", strides=1):
    us = keras.layers.UpSampling2D((2, 2))(x)
    concat = keras.layers.Concatenate()([us, skip])
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(concat)
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(c)
    return c

def bottleneck(x, filters, kernel_size=(3, 3), padding="same", strides=1):
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(x)
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(c)
    return c

image_size = 384
def UNet():
    f = [16, 32, 64, 128, 256, 512]
    inputs = keras.layers.Input((image_size, image_size, 4))
    
    p0 = inputs
    c1, p1 = down_block(p0, f[0]) #128 -> 64
    c2, p2 = down_block(p1, f[1]) #64 -> 32
    c3, p3 = down_block(p2, f[2]) #32 -> 16
    c4, p4 = down_block(p3, f[3]) #16 -> 8
    c5, p5 = down_block(p4, f[4]) #8 -> 4
    
    bn = bottleneck(p5, f[5])
    
    u1 = up_block(bn, c5, f[4]) #4 -> 8
    u2 = up_block(u1, c4, f[3]) #8 -> 16
    u3 = up_block(u2, c3, f[2]) #16 -> 32
    u4 = up_block(u3, c2, f[1]) #32 -> 64
    u5 = up_block(u4, c1, f[0]) #64 -> 128
    
    outputs = keras.layers.Conv2D(1, (1, 1), padding="same", activation="sigmoid")(u5)
    model = keras.models.Model(inputs, outputs)
    return model

model = UNet()
opt = keras.optimizers.Adam()
model.compile(optimizer=opt, loss="binary_crossentropy", metrics=["acc"])
model.summary()

hist = model.fit(x, y, validation_split = 0.2, batch_size=32,epochs=25)

plt.figure(figsize=(15,7))
plt.rcParams['font.size'] = '20'
plt.plot(hist.history['acc'])
plt.plot(hist.history['val_acc'])
plt.title('model accuracy')
plt.ylabel('accuracy')
plt.xlabel('epoch')
plt.grid()
plt.legend(['train', 'test'], loc='upper left')
plt.show()
# summarize history for loss
plt.figure(figsize=(15,7))
plt.plot(hist.history['loss'])
plt.rcParams['font.size'] = '20'
plt.plot(hist.history['val_loss'])
plt.title('model loss')
plt.ylabel('loss')
plt.grid()
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
plt.show()

x1 = [];y1 = []
for i in range(1000,1200):
    x, y = data[i]
    x1.append(x.numpy())
    y1.append(y.numpy())

x1 = np.array(x1)
y_test = np.array(y1)
x_test = np.moveaxis(x1, 1, -1)
result = model.predict(x_test)

for i in range(result.shape[0]):
  temp = cv2.threshold(result[i], 0.5, 1, cv2.THRESH_BINARY)[1]
  result[i] = np.expand_dims(temp,axis = 2)

r = 151
plt.rcParams['font.size'] = '20'
fig = plt.figure(figsize = (20,15))
fig.subplots_adjust(hspace=0.4, wspace=0.4)
ax = fig.add_subplot(1, 3, 1)
ax.imshow(x_test[r,:,:,:3])
plt.title('Test Image', fontsize=20)
plt.xlabel('',fontsize=20)
plt.ylabel('',fontsize=20)
ax = fig.add_subplot(1, 3, 2)
ax.imshow(np.reshape(y_test[r], (384, 384)), cmap="gray")
plt.title('Binary Mask', fontsize=20)
plt.xlabel('',fontsize=14)
plt.ylabel('',fontsize=14)
ax = fig.add_subplot(1, 3, 3)
ax.imshow(np.reshape(result[r], (384, 384)), cmap="gray")
plt.title('Predicted Mask', fontsize=20)
plt.xlabel('',fontsize=14)
plt.ylabel('',fontsize=14)

"""# **Case 3. Double convolution in each up-sampling and down-sampling blocks. 4 layer blocks, initial feature map = 16 .**"""

import tensorflow as tf
from tensorflow import keras
def down_block(x, filters, kernel_size=(3, 3), padding="same", strides=1):
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(x)
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(c)
    p = keras.layers.MaxPool2D((2, 2), (2, 2))(c)
    return c, p

def up_block(x, skip, filters, kernel_size=(3, 3), padding="same", strides=1):
    us = keras.layers.UpSampling2D((2, 2))(x)
    concat = keras.layers.Concatenate()([us, skip])
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(concat)
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(c)
    return c

def bottleneck(x, filters, kernel_size=(3, 3), padding="same", strides=1):
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(x)
    c = keras.layers.Conv2D(filters, kernel_size, padding=padding, strides=strides, activation="relu")(c)
    return c

image_size = 384
def UNet():
    f = [16, 32, 64, 128, 256]
    inputs = keras.layers.Input((image_size, image_size, 4))
    
    p0 = inputs
    c1, p1 = down_block(p0, f[0]) #128 -> 64
    c2, p2 = down_block(p1, f[1]) #64 -> 32
    c3, p3 = down_block(p2, f[2]) #32 -> 16
    c4, p4 = down_block(p3, f[3]) #16 -> 8
    #c5, p5 = down_block(p4, f[4]) #8 -> 4
    
    bn = bottleneck(p4, f[4])
    
    #u1 = up_block(bn, c5, f[4]) #4 -> 8
    u2 = up_block(bn, c4, f[3]) #8 -> 16
    u3 = up_block(u2, c3, f[2]) #16 -> 32
    u4 = up_block(u3, c2, f[1]) #32 -> 64
    u5 = up_block(u4, c1, f[0]) #64 -> 128
    
    outputs = keras.layers.Conv2D(1, (1, 1), padding="same", activation="sigmoid")(u5)
    model = keras.models.Model(inputs, outputs)
    return model

model = UNet()
opt = keras.optimizers.
model.compile(optimizer=opt, loss="binary_crossentropy", metrics=["acc"])
model.summary()

hist = model.fit(x, y, validation_split = 0.2, batch_size=32,epochs=5)

plt.figure(figsize=(15,7))
plt.rcParams['font.size'] = '20'
plt.plot(hist.history['acc'])
plt.plot(hist.history['val_acc'])
plt.title('model accuracy')
plt.ylabel('accuracy')
plt.xlabel('epoch')
plt.grid()
plt.legend(['train', 'test'], loc='upper left')
plt.show()
# summarize history for loss
plt.figure(figsize=(15,7))
plt.plot(hist.history['loss'])
plt.rcParams['font.size'] = '20'
plt.plot(hist.history['val_loss'])
plt.title('model loss')
plt.ylabel('loss')
plt.grid()
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
plt.show()

x1 = [];y1 = []
for i in range(1000,1200):
    x, y = data[i]
    x1.append(x.numpy())
    y1.append(y.numpy())

x1 = np.array(x1)
y_test = np.array(y1)
x_test = np.moveaxis(x1, 1, -1)

result = model.predict(x_test)

import cv2
for i in range(result.shape[0]):
  temp = cv2.threshold(result[i], 0.5, 1, cv2.THRESH_BINARY)[1]
  result[i] = np.expand_dims(temp,axis = 2)

import random
random.seed = 125
# r = random.randint(0, len(x_test)-1)
r = 100
fig = plt.figure(figsize = (20,15))
fig.subplots_adjust(hspace=0.4, wspace=0.4)
ax = fig.add_subplot(1, 3, 1)
ax.imshow(x_test[r,:,:,:3])
plt.title('Test Image')
ax = fig.add_subplot(1, 3, 2)
ax.imshow(np.reshape(y_test[r], (384, 384)), cmap="gray")
plt.title('Binary Mask')
ax = fig.add_subplot(1, 3, 3)
ax.imshow(np.reshape(result[r], (384, 384)), cmap="gray")
plt.title('Predicted Mask')