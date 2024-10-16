# -*- coding: utf-8 -*-
"""Untitled14-3.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/18BeaCBMlHELVluxRhvghFOFZfGkdCmzJ
"""

import os
import random
import numpy as np
import matplotlib.pyplot as plt
import cv2

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import datasets, models, transforms
from torch.utils.data import Dataset, DataLoader
from torchsummary import summary
from tqdm import tqdm

!wget http://www.robots.ox.ac.uk/~vgg/data/pets/data/images.tar.gz
!wget http://www.robots.ox.ac.uk/~vgg/data/pets/data/annotations.tar.gz
!tar -xf images.tar.gz
!tar -xf annotations.tar.gz

from PIL import Image

num_skipped = 0

images_folder_path = "images"
target_folder_path = os.path.join("annotations", "trimaps")

for fname in os.listdir(images_folder_path):
    if fname.endswith(".jpg"):
      fpath = os.path.join(images_folder_path, fname)
      target_fpath = os.path.join(target_folder_path, fname.replace(".jpg", ".png"))

      with Image.open(fpath) as image:
          im = np.asarray(image)
          bad_size = True if im.ndim < 3 else False

      if bad_size:
          num_skipped += 1
          print(fpath)
          print(target_fpath)
          # Delete corrupted image
          os.remove(fpath)
          os.remove(target_fpath)

print(f"Deleted {num_skipped} images.")

import os
from glob import glob

input_dir = "images/"
target_dir = "annotations/trimaps/"

input_img_paths = sorted(glob(input_dir + "/*.jpg"))
target_paths = sorted(glob(target_dir + "/*.png"))

len(input_img_paths)

img = cv2.imread(input_img_paths[12])[:, : , ::-1]

plt.axis("off")
plt.imshow(img)

img.shape

# 1 (forgrounf)
# 2 (background)
# 3 (contour)

def display_target(target_array):
    normalized_array = (target_array.astype("uint8") - 1) * 127  # 0 , 127, 254
    plt.axis("off")
    plt.imshow(normalized_array[:, :, 0])

annotation = cv2.imread(target_paths[12])
display_target(annotation)

class SegmentDataset(Dataset):
    def __init__(self, img_path, target_path, img_size=(200, 200),
                 random_state=1337, train=True, transform=None):

        all_img_path = sorted(glob(img_path + "/*.jpg"))
        all_target_path = sorted(glob(target_path + "/*.png"))

        random.Random(random_state).shuffle(all_img_path)
        random.Random(random_state).shuffle(all_target_path)

        self.img_size = img_size
        self.transform = transform

        num_val_sample = 1000

        self.img_path = all_img_path[num_val_sample:] if train else all_img_path[:num_val_sample]
        self.target_path = all_target_path[num_val_sample:] if train else all_target_path[:num_val_sample]

    def __len__(self):
        return len(self.img_path)

    def img_read(self, path):
        img = cv2.imread(path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, self.img_size)
        return img

    def __getitem__(self, indx):
        img_path = self.img_path[indx]
        target_path = self.target_path[indx]
        img = self.img_read(img_path)
        target = self.img_read(target_path)[:, :, 0]
        target = torch.from_numpy(target.astype("uint8")) - 1
        if self.transform:
            img = self.transform(img)
        else:
            img = transforms.ToTensor()(img)
        return img.float(), target.long()

batch_size = 64
input_dir = "images/"
target_dir = "annotations/trimaps/"

train_ds = SegmentDataset(input_dir, target_dir, train=True)
val_ds = SegmentDataset(input_dir, target_dir, train=False)

train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
val_dl = DataLoader(val_ds, batch_size=batch_size)

imgs, targets = next(iter(train_dl))

plt.imshow(imgs[0].permute(1, 2, 0))

plt.imshow(targets[0] * 127)

x = torch.randn(1, 64, 16, 16)
conv_out = nn.Conv2d(64, 64, 3, stride=2, padding=1)(x)
nn.ConvTranspose2d(64, 64, 3, stride=2, padding=1, output_padding=1)(conv_out).size()

class DoubleConv2d(nn.Module):
    def __init__(self, in_channel, out_channel):
        super().__init__()
        self.cn1 = nn.Conv2d(in_channel, out_channel, stride=2,
                             kernel_size=3, padding=1)
        self.cn2 = nn.Conv2d(out_channel, out_channel,
                             kernel_size=3, padding=1)

    def forward(self, x):
        x = F.relu(self.cn1(x))
        x = F.relu(self.cn2(x))
        return x


class DoubleConvTranspose2d(nn.Module):
    def __init__(self, in_channel, out_channel):
        super().__init__()
        self.cn1 = nn.ConvTranspose2d(in_channel, out_channel,
                             kernel_size=3, padding=1)
        self.cn2 = nn.ConvTranspose2d(out_channel, out_channel, stride=2,
                             kernel_size=3, padding=1, output_padding=1)

    def forward(self, x):
        x = F.relu(self.cn1(x))
        x = F.relu(self.cn2(x))
        return x


# Encoder 64, 64, 128, 128, 256, 256
class SegmentNet(nn.Module):
    def __init__(self, in_channel, num_classes):
        super().__init__()
        self.encoder = nn.Sequential(
            DoubleConv2d(3, 64),
            DoubleConv2d(64, 128),
            DoubleConv2d(128, 256),
        )

        self.decoder = nn.Sequential(
            DoubleConvTranspose2d(256, 256),
            DoubleConvTranspose2d(256, 128),
            DoubleConvTranspose2d(128, 64),
        )

        self.output_block = nn.Conv2d(64, num_classes, 3, 1, 1) # if num_classes =3 , per pixel ==> [0.2, -1.2, 3.1]

    def forward(self, x):
        x = self.encoder(x)
        x = self.decoder(x)
        x = self.output_block(x)
        return x

model = SegmentNet(3, 3)
summary(model, (3, 200, 200), device="cpu")

device = "cuda" if torch.cuda.is_available() else "cpu"
device

learning_rate = 0.001


model = SegmentNet(3, 3).to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

epoch_nums = 50


for epoch in range(epoch_nums):
    train_loss = 0.0
    for imgs, annotations in tqdm(train_dl):
        imgs, annotations = imgs.to(device), annotations.to(device)
        predictions = model(imgs)
        loss = criterion(predictions, annotations)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        train_loss += loss.item()
    print(f"Epoch {epoch+1}/{epoch_nums} | train loss: {train_loss/len(train_dl)}")
