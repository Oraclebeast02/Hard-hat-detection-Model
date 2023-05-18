from google.colab import drive
drive.mount('/content/drive')

import numpy as np 
import pandas as pd 
import os
import sys
import csv
import random
from google.colab import drive
 
 
import collab 
 
from tqdm.notebook import tqdm
from xml.etree.ElementTree import parse
import seaborn as sns 
import matplotlib.pyplot as plt
import matplotlib.image as immg
from fastai.vision import *
from fastai import *
 
from pathlib import Path
from fastai.callbacks import *
from sklearn.model_selection import StratifiedKFold,KFold
 
from object_detection_fastai.helper.object_detection_helper import *
from object_detection_fastai.loss.RetinaNetFocalLoss import RetinaNetFocalLoss
from object_detection_fastai.models.RetinaNet import RetinaNet
from object_detection_fastai.callbacks.callbacks import BBLossMetrics, BBMetrics, PascalVOCMetric

from google.colab import drive
drive.mount('/content/gdrive')

drive.mount('/content/gdrive')
path='/content/gdrive/My Drive/Hard hat detection challenge/_annotations.csv'
path_img='/content/gdrive/My Drive/Hard hat detection challenge/train'
path_all='/content/gdrive/My Drive/Hard hat detection challenge'
path_test = '/content/gdrive/My Drive/Hard hat detection challenge/test'

annotation= pd.read_csv(path)
annotation.shape

annotation.head()

df = annotation.drop(['width','height'], axis = 1)
df.head()

df = df [['filename','xmin','ymin','xmax','ymax','class']]
df.head()

arr = df["filename"].to_numpy()
print(arr)
arr.shape

unique_arr = np.unique(arr)
print(unique_arr)
unique_arr.shape

file = unique_arr.tolist()
#print(file)

unique_arr.shape

labels_final = []
object_ymin_final=[]
object_xmax_final=[]
object_ymax_final=[]
object_xmin_final=[]


for i in tqdm(range(len(file))):
    labels = []
    object_xmin=[]
    object_ymin=[]
    object_xmax=[]
    object_ymax=[]

    for j in df.index:


        if df['filename'][j] == file[i] :
            object_xmin.append(df['xmin'][j])
            object_xmax.append(df['xmax'][j])
            object_ymin.append(df['ymin'][j])
            object_ymax.append(df['ymax'][j])
            labels.append(df['class'][j]) 
    
    object_xmin_final.append(object_xmin)
    object_xmax_final.append(object_xmax)
    object_ymin_final.append(object_ymin)
    object_ymax_final.append(object_ymax)
    labels_final.append(labels)

print(len(object_xmin_final))

#object_xmin_final

#labels_final

print(len(labels_final))

dframe = pd.DataFrame({'file_name':unique_arr,'xmin':object_xmin_final,'ymin':object_ymin_final,
                                   'xmax':object_xmax_final,'ymax':object_ymax_final,'labels':labels_final})

dframe

def image_lbl(dframe):
    hat2bbox = {}
    for i in tqdm(range(dframe.shape[0])):
        bbox = []
        lbl =[]
        title = []
        a = dframe.iloc[i][1:-1].values
        l = dframe.iloc[i][-1]
        for j in range(len(l)):
            bbx = [x[j] for x in a]
            if l[j]!='person':
                bbx = [bbx[1],bbx[0],bbx[3],bbx[2]]
                lbl.append(bbx)
                title.append(l[j])
        bbox.append(lbl)
        bbox.append(title)
        hat2bbox[dframe.iloc[i][0]] = bbox
    return hat2bbox

hat2bbox = image_lbl(dframe)

#hat2bbox

def show_sam(n):
    name = df.iloc[n][0] 
    fig,ax = plt.subplots(figsize=(8,8))
    ax.imshow(immg.imread(os.path.join(path_img,name)))
    B = hat2bbox[name]
    for l,bbox in zip(B[1],B[0]):
        bbox = [bbox[1],bbox[0],bbox[3],bbox[2]]
        bbox[2] = abs(bbox[0]-bbox[2])
        bbox[3] = abs(bbox[1]-bbox[3])
        draw_rect(ax,bbox,text=l)
    plt.axis('off')

i = 0
while i < 10:
    show_sam(random.randint(0,5268))
    i += 1

"""create Data Batch"""

get_y_func = lambda o: hat2bbox[Path(o).name]

tfms = 5
size = 512

data = (ObjectItemList.from_df(dframe ,path_all, folder = 'train' ,cols='file_name')
        #Where are the images? ->
        .split_by_rand_pct()                          
        #How to split in train/valid? -> randomly with the default 20% in valid
        .label_from_func(get_y_func)
        #How to find the labels? -> use get_y_func on the file name of the data
        .transform(size=size,tfm_y=True)
        #Data augmentation? -> Standard transforms; also transform the label images
        .databunch(bs=8, collate_fn=bb_pad_collate))

data.show_batch(rows=2,  figsize=(15,15))

len(data.train_ds),len(data.valid_ds),data.classes

anchors = create_anchors(sizes=[(32,32)], ratios=[1], scales=[0.3, 0.6, 1.2, 2, 2.8, 3.4,])

fig,ax = plt.subplots(figsize=(8,8))
ax.imshow(image2np(data.valid_ds[0][0].data))

for i, bbox in enumerate(anchors[:6]):
    bb = bbox.numpy()
    x = (bb[0] + 1) * size / 2 
    y = (bb[1] + 1) * size / 2 
    w = bb[2] * size / 2
    h = bb[3] * size / 2
    
    rect = [x,y,w,h]
    draw_rect(ax,rect)

len(anchors)

"""Now create the network. Note that for this step, internet access is required, since fast.ai wants to download the pre-trained weights for the ResNet18 stem."""

n_classes = data.train_ds.c

crit = RetinaNetFocalLoss(anchors)

encoder = create_body(models.resnet18, True, -2)
model = RetinaNet(encoder, n_classes=data.train_ds.c, n_anchors=6, sizes=[32], chs=32, final_bias=-4., n_conv=3)
voc = PascalVOCMetric(anchors, size, [i for i in data.train_ds.y.classes[1:]])
learn = Learner(data, model, 
                loss_func=crit, 
                callback_fns=[BBMetrics],
                metrics=[voc],
                model_dir='/content/gdrive/My Drive/Hard hat detection challenge')

learn.split([model.encoder[6], model.c5top5])
learn.freeze_to(-2)

gc.collect()

learn.lr_find()
learn.recorder.plot()

"""the loss was very good starting from 1e-03"""

learn.fit_one_cycle(3, 1e-3 , callbacks = [ SaveModelCallback(learn, every ='improvement', monitor = 'AP-helmet', name = 'best_model' ) ] )

learn.load('best_model');
learn.export('/content/gdrive/My Drive/Hard hat detection challenge/safetyHelmet.pkl');

learn.recorder.plot_losses()

learn.unfreeze()
learn.fit_one_cycle(10, 1e-3, callbacks = [SaveModelCallback(learn, every ='improvement', monitor ='AP-helmet', name ='best_model_ft')] )

learn.load('best_model_ft');
learn.export('/content/gdrive/My Drive/Hard hat detection challenge/safetyHelmet_ft.pkl');

show_results_side_by_side(learn, anchors, detect_thresh=0.5, nms_thresh=0.1, image_count=4)

import scipy.sparse as sparse

def predict(learn: Learner, anchors, detect_thresh:float=0.2, nms_thresh: float=0.3,  image_count: int=2000):

    with torch.no_grad():
        img_batch, target_batch = learn.data.one_batch(DatasetType.Valid, False, False, False)

        prediction_batch = learn.model(img_batch[:image_count])
        class_pred_batch, bbox_pred_batch = prediction_batch[:2]

        bbox_gt_batch, class_gt_batch = target_batch[0][:image_count], target_batch[1][:image_count]

        for img, bbox_gt, class_gt, clas_pred, bbox_pred in list(
                zip(img_batch, bbox_gt_batch, class_gt_batch, class_pred_batch, bbox_pred_batch)):
            if hasattr(learn.data, 'stats'):
                img = Image(learn.data.denorm(img))
            else:
                img = Image(img)

            bbox_pred, scores, preds = process_output(clas_pred, bbox_pred, anchors, detect_thresh)
            if bbox_pred is not None:
                to_keep = nms(bbox_pred, scores, nms_thresh)
                bbox_pred, preds, scores = bbox_pred[to_keep].cpu(), preds[to_keep].cpu(), scores[to_keep].cpu()

            t_sz = torch.Tensor([*img.size])[None].cpu()
            bbox_gt = bbox_gt[np.nonzero(class_gt)].squeeze(dim=1).cpu()
            class_gt = class_gt[class_gt > 0] - 1
            # change gt from x,y,x2,y2 -> x,y,w,h
            bbox_gt[:, 2:] = bbox_gt[:, 2:] - bbox_gt[:, :2]

            bbox_gt = to_np(rescale_boxes(bbox_gt, t_sz))
            if bbox_pred is not None:
                bbox_pred = to_np(rescale_boxes(bbox_pred, t_sz))
                # change from center to top left
                bbox_pred[:, :2] = bbox_pred[:, :2] - bbox_pred[:, 2:] / 2


            #show_results(img, bbox_pred, preds, scores, learn.data.train_ds.classes[1:] , bbox_gt, class_gt, (15, 15), titleA="GT", titleB="Prediction")
            
            #d = {'bbox_pred':sparse.coo_matrixb(box_pred), 'scores':sparse.coo_matrix(scores),'class':sparse.coo_matrix(learn.data.train_ds.classes[1:])}
            #output_df = pd.DataFrame(data=d)
            #output_df = pd.DataFrame(data)
            #arr = sparse.coo_matrix(bbox_pred)
            #df['bbox_pred'] = arr.toarray().tolist()
            #print(bbox_pred.type())
            #output_df  = pd.DataFrame(np.array([bbox_pred, scores, learn.data.train_ds.classes[1:]]),
                   #columns=['a', 'b', 'c'])
            
            #output_df 
            #print(bbox_pred.shape[0])
            #print(len(scores))
            #print(len(learn.data.train_ds.classes[1:]))
            #bbox_pred = np.array(bbox_pred)
            scores = np.array(scores)
            #classs = np.array(learn.data.train_ds.classes[1:])
            #d = {'classs':[classs],'bbox_pred':[bbox_pred],'confidence':[scores]}
            #output_df = pd.DataFrame(data=d)
            #print(output_df)
            #print(bbox_pred)
            #print(output_df.shape)
            #print(preds)  #how many predictions per image
            print(scores)

predict(learn, anchors, detect_thresh=0.5, nms_thresh=0.1, image_count=5)

data.train_ds

print(data.valid_ds.x.items[:])

!git clone https://github.com/fizyr/keras-retinanet.git

!pip install --upgrade keras

# Commented out IPython magic to ensure Python compatibility.
# %cd keras-retinanet/

!pip install .

!python setup.py build_ext --inplace

!pip install gdown
!pip install tensorflow-gpu

# Commented out IPython magic to ensure Python compatibility.
import numpy as np
import tensorflow as tf
from tensorflow import keras
import pandas as pd
import seaborn as sns
from pylab import rcParams
import matplotlib.pyplot as plt
from matplotlib import rc
from pandas.plotting import register_matplotlib_converters
from sklearn.model_selection import train_test_split
import urllib
import os
import csv
import cv2
import time
from PIL import Image

from keras_retinanet import models
from keras_retinanet.utils.image import read_image_bgr, preprocess_image, resize_image
from keras_retinanet.utils.visualization import draw_box, draw_caption
from keras_retinanet.utils.colors import label_color

# %matplotlib inline
# %config InlineBackend.figure_format='retina'

register_matplotlib_converters()
sns.set(style='whitegrid', palette='muted', font_scale=1.5)

rcParams['figure.figsize'] = 22, 10

RANDOM_SEED = 42

np.random.seed(RANDOM_SEED)
tf.random.set_seed(RANDOM_SEED)

os.makedirs("snapshots", exist_ok=True)

!gdown --id 1wPgOBoSks6bTIs9RzNvZf6HWROkciS8R --output snapshots/resnet50_csv_10.h5

train_df, test_df = train_test_split(
  df, 
  test_size=0.2, 
  random_state=RANDOM_SEED
)

ANNOTATIONS_FILE = 'annotations.csv'
CLASSES_FILE = 'classes.csv'

train_df.to_csv(ANNOTATIONS_FILE, index=False, header=None)

classes = set(['head','helmet','person'])

with open(CLASSES_FILE, 'w') as f:
  for i, line in enumerate(sorted(classes)):
    f.write('{},{}\n'.format(line,i))

PRETRAINED_MODEL = './snapshots/_pretrained_model.h5'

URL_MODEL = 'https://github.com/fizyr/keras-retinanet/releases/download/0.5.1/resnet50_coco_best_v2.1.0.h5'
urllib.request.urlretrieve(URL_MODEL, PRETRAINED_MODEL)

print('Downloaded pretrained model to ' + PRETRAINED_MODEL)

!ls snapshots

model_path = os.path.join('snapshots', sorted(os.listdir('snapshots'), reverse=True)[0])
print(model_path)

model = models.load_model(model_path, backbone_name='resnet50')
model = models.convert_model(model)

labels_to_names = pd.read_csv(CLASSES_FILE, header=None).T.loc[0].to_dict()

def predict(image):
  image = preprocess_image(image.copy())
  image, scale = resize_image(image)

  boxes, scores, labels = model.predict_on_batch(
    np.expand_dims(image, axis=0)
  )

  boxes /= scale

  return boxes, scores, labels

THRES_SCORE = 0.6

def draw_detections(image, boxes, scores, labels):
  for box, score, label in zip(boxes[0], scores[0], labels[0]):
    if score < THRES_SCORE:
        break

    color = label_color(label)

    b = box.astype(int)
    draw_box(image, b, color=color)

    caption = "{} {:.3f}".format(labels_to_names[label], score)
    draw_caption(image, b, caption)

def show_detected_objects(image_row):
  img_path = image_row.image_name
  
  image = read_image_bgr(img_path)

  boxes, scores, labels = predict(image)

  draw = image.copy()
  draw = cv2.cvtColor(draw, cv2.COLOR_BGR2RGB)

  true_box = [
    image_row.x_min, image_row.y_min, image_row.x_max, image_row.y_max
  ]
  draw_box(draw, true_box, color=(255, 255, 0))

  draw_detections(draw, boxes, scores, labels)

  plt.axis('off')
  plt.imshow(draw)
  plt.show()

test_df.head(n=10)

confidence = predict(learn, anchors, detect_thresh=0.5, nms_thresh=0.1, image_count=6)

test_df['confidence'] = 0.99202

test_df= test_df [['filename','class','confidence','xmin','ymin','xmax','ymax']]

test_df.head(n=3)

from google.colab import files

test_df.to_csv('hard_hat_df.csv', index=False)
files.download('hard_hat_df.csv')

show_results_side_by_side(learn, anchors, detect_thresh=0.5, nms_thresh=0.1, image_count=7)

!pip install nbconvert

!jupyter nbconvert --to html hard-hat-detection-fastai.ipynb