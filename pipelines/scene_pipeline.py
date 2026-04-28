from torchvision.transforms import Compose

from MiDaS.midas.dpt_depth import DPTDepthModel
from database.sqlite import SqliteDatabase
import cv2
import base64
import numpy as np
import logging
from ultralytics import YOLO
import torch
import math
from dataclasses import dataclass


class SceneProcessor:
    def __init__(self, database: SqliteDatabase):
        self.database = database

    def get_all_scenes(self):
        return self.database.get_all_scenes()

    def decode_image(self, b64_image):
        # Step 1: Decode the base64 string to bytes
        image_bytes = base64.b64decode(b64_image)
        # Step 2: Convert bytes to a NumPy array using OpenCV
        image_array = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        # Step 3: Convert BGR to RGB (OpenCV uses BGR by default, Matplotlib uses RGB)
        image_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
        return image_rgb

class ObjectDetectionProcessor:
    def __init__(self, model_path):
        self.model = YOLO(model_path)

    def detect(self, image):
        results = self.model(image)
        print(results[0].boxes)
        for box in results[0].boxes:
            # Class ID and name
            cls_id = int(box.cls)
            class_name = self.model.names[cls_id]
            # Confidence score
            confidence = box.conf.item()
            # Bounding box coordinates (xyxy format: [x1, y1, x2, y2])
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Print the results
            print(f"Class: {class_name}")
            print(f"Confidence: {confidence:.2f}")
            print(f"Bounding Box (xyxy): x1={x1}, y1={y1}, x2={x2}, y2={y2}")
            print(f"Width: {x2 - x1}, Height: {y2 - y1}")
            print("---")
        return results

    def compare_distance_between_objects(self, box1, box2):
        # Unpack: x, y (top-left), h, w
        x1, y1, h1, w1 = box1
        x2, y2, h2, w2 = box2

        # Calculate 1D distances
        # For X: distance between (x1 + w1) and x2 OR (x2 + w2) and x1
        dx = max(0, x1 - (x2 + w2), x2 - (x1 + w1))

        # For Y: distance between (y1 + h1) and y2 OR (y2 + h2) and y1
        dy = max(0, y1 - (y2 + h2), y2 - (y1 + h1))

        # If both dx and dy are 0, they overlap = distance is 0
        return math.sqrt(dx ** 2 + dy ** 2)

class DepthDetectionProcessor:
    def __init__(self, model, transform, device):
        self.model = model
        self.transform = transform
        self.device = device

    def detect(self, image_bgr):
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB) / 255.0
        sample = self.transform({"image": image_rgb})["image"]

        with torch.no_grad():
            prediction = self.model.forward(torch.from_numpy(sample).to(self.device).unsqueeze(0))
            depth = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=image_rgb.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze().cpu().numpy()

        depth_map = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        return depth_map

    def compare_depth_mean(self,depth_map, x1_y1_h1_w1, x2_y2_h2_w2):
        """
        :param depth_map: depth map of the image
        :param x1_y1_h1_w1: coordinates of the first bounding box
        :param x2_y2_h2_w2: coordinates of the second bounding box
        :return: absolute difference between the mean of the two bounding boxes
        """
        x1, y1, h1, w1 = x1_y1_h1_w1
        x2, y2, h2, w2 = x2_y2_h2_w2

        img1_box = depth_map[y1:y1 + h1, x1:x1 + w1]
        img2_box = depth_map[y2:y2 + h2, x2:x2 + w2]

        img1_mean = np.mean(img1_box)
        img2_mean = np.mean(img2_box)

        difference = abs(img1_mean - img2_mean)
        return difference

    def compare_depth_percentile(self, depth_map, x1_y1_h1_w1: tuple, x2_y2_h2_w2: tuple, percentile: int = 10):
        """
        :param depth_map: depth map of the image
        :param x1_y1_h1_w1: coordinates of the first bounding box
        :param x2_y2_h2_w2: coordinates of the second bounding box
        :return:
        """
        x1, y1, h1, w1 = x1_y1_h1_w1
        x2, y2, h2, w2 = x2_y2_h2_w2

        img1_box = depth_map[y1:y1 + h1, x1:x1 + w1]
        img2_box = depth_map[y2:y2 + h2, x2:x2 + w2]

        img1_percentile = np.percentile(img1_box, percentile)
        img2_percentile = np.percentile(img2_box, percentile)

        difference = abs(img1_percentile - img2_percentile)
        return difference

class Visualizer:
    def __init__(self):
        pass
    def visualize(self, image, depth_map, scene_bounding_boxes, object_bounding_boxes):
        pass

class ScenePipeline:
    def __init__(self, database: SqliteDatabase,
                 depth_model,
                 depth_transform,
                 depth_device = "cpu",
                 yolo_model_path: str = "yolov8n.pt",
                 depth_detection_method: str = "percentile"
                 ):
        self.database = database
        self.scene_processor = SceneProcessor(self.database)
        self.object_detection_processor = ObjectDetectionProcessor(yolo_model_path)
        self.depth_detection_processor = DepthDetectionProcessor(depth_model,depth_transform,depth_device)
        self.visualizer = Visualizer()
        self.depth_detection_method = depth_detection_method
        self.yolo_model_path = yolo_model_path
        self.depth_model = depth_model
        self.depth_transform = depth_transform
        self.depth_device = depth_device

    def run(self):
        scenes = self.scene_processor.get_all_scenes() # getting all scenes and processing one by one
        for scene in scenes:
            print(scene.scene_id)
            image_bgr = self.scene_processor.decode_image(scene.image) # get the frame from the database
            restricted_zones = scene.red_zones # get the red zones from the database
            depth_map = self.depth_detection_processor.detect(image_bgr) # run the depth detection model
            object_detection_results = self.object_detection_processor.detect(image_bgr) # detect objects in the frame

            for zone in restricted_zones:
                for obj in object_detection_results:
                    if self.depth_detection_method == "mean":
                        depth_difference = self.depth_detection_processor.compare_depth_mean(depth_map, zone, obj.xyxy)
                    if self.depth_detection_method == "percentile":
                        depth_difference = self.depth_detection_processor.compare_depth_percentile(depth_map, zone, obj.xyxy)

@dataclass
class ScenePipelineConfig:
    database: SqliteDatabase
    scene_processor: SceneProcessor
    object_detection_processor: ObjectDetectionProcessor
    depth_detection_processor: DepthDetectionProcessor
    visualizer: Visualizer
    depth_model: DPTDepthModel
    depth_transform: Compose
    depth_device: torch.device
    depth_detection_method: tuple = ("percentile", 10)
    yolo_model_path: str = "yolov8n.pt"

