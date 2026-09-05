import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List


class ConvBlock(nn.Module):
    """Standard Convolutional Block with BatchNorm and ReLU."""
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.pool(self.relu(self.bn(self.conv(x))))


class BrainMRIClassifier(nn.Module):
    """
    Production-ready Brain MRI Abnormality & Tumor Classifier.
    Supports 4 target classes:
    0: 'no_tumor'
    1: 'glioma'
    2: 'meningioma'
    3: 'pituitary'
    """
    def __init__(self, num_classes: int = 4, in_channels: int = 3):
        super().__init__()
        # Feature extraction layers
        self.layer1 = ConvBlock(in_channels, 64)
        self.layer2 = ConvBlock(64, 128)
        self.layer3 = ConvBlock(128, 256)
        self.layer4 = ConvBlock(256, 512)
        
        # Target layer for Grad-CAM explainability hooks
        self.target_conv_layer = self.layer4.conv

        # Adaptive pooling & Classifier head
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Sequential(
            nn.Dropout(p=0.4),
            nn.Linear(512, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.3),
            nn.Linear(256, num_classes),
        )

    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        return x

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.forward_features(x)
        pooled = self.avgpool(features)
        flattened = torch.flatten(pooled, 1)
        logits = self.classifier(flattened)
        return logits
