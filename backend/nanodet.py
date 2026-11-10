"""CPU benchmark adapter for OpenCV Zoo NanoDet (fixed COCO categories).

Model/preprocessing reference: https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_nanodet
This is a comparison candidate, not the gallery's selected detector.
"""
import cv2
import numpy as np
from backend.detection import ROOT, filter_boxes

COCO = ('person,bicycle,car,motorcycle,airplane,bus,train,truck,boat,traffic light,fire hydrant,stop sign,parking meter,bench,bird,cat,dog,horse,sheep,cow,elephant,bear,zebra,giraffe,backpack,umbrella,handbag,tie,suitcase,frisbee,skis,snowboard,sports ball,kite,baseball bat,baseball glove,skateboard,surfboard,tennis racket,bottle,wine glass,cup,fork,knife,spoon,bowl,banana,apple,sandwich,orange,broccoli,carrot,hot dog,pizza,donut,cake,chair,couch,potted plant,bed,dining table,toilet,tv,laptop,mouse,remote,keyboard,cell phone,microwave,oven,toaster,sink,refrigerator,book,clock,vase,scissors,teddy bear,hair drier,toothbrush').split(',')


class NanoDetector:
    name = 'nanodet'

    def __init__(self):
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.log_severity_level = 3
        self.session = ort.InferenceSession(str(ROOT / 'nanodet' / 'object_detection_nanodet_2022nov.onnx'), options, providers=['CPUExecutionProvider'])

    def detect(self, image, prompt=None):
        h, w = image.shape[:2]
        # Letterbox keeps shapes intact; undo padding before returning coordinates.
        scale = 416 / max(h, w)
        resized_w, resized_h = round(w*scale), round(h*scale)
        left, top = (416-resized_w)//2, (416-resized_h)//2
        padded = np.zeros((416,416,3), dtype=np.uint8)
        padded[top:top+resized_h, left:left+resized_w] = cv2.resize(image, (resized_w,resized_h))
        pixels = ((padded.astype(np.float32)-np.array([103.53,116.28,123.675],np.float32))/np.array([57.375,57.12,58.395],np.float32)).transpose(2,0,1)[None]
        outputs = self.session.run(None, {self.session.get_inputs()[0].name:pixels})
        scores = sorted((x[0] for x in outputs if x.shape[-1] == 80), key=len, reverse=True)
        distances = sorted((x[0] for x in outputs if x.shape[-1] == 32), key=len, reverse=True)
        rows = []
        for stride, classes, distance in zip((8,16,32,64), scores, distances):
            size = 416 // stride
            yy, xx = np.mgrid[:size,:size]
            centers = np.column_stack((xx.ravel(),yy.ravel()))*stride+.5*(stride-1)
            keep = classes.max(axis=1) >= .35
            classes, centers, distance = classes[keep], centers[keep], distance[keep]
            distribution = distance.reshape(-1,4,8)
            distribution = np.exp(distribution-distribution.max(axis=-1, keepdims=True))
            distance = (distribution/distribution.sum(axis=-1,keepdims=True) @ np.arange(8))*stride
            for center, dist, cls in zip(centers, distance, classes):
                x,y = center
                box = [(x-dist[0]-left)/resized_w,(y-dist[1]-top)/resized_h,
                       (x+dist[2]-left)/resized_w,(y+dist[3]-top)/resized_h]
                rows.append({'box':box,'label':COCO[int(cls.argmax())],'score':float(cls.max())})
        return filter_boxes(rows,w,h,threshold=.35)
