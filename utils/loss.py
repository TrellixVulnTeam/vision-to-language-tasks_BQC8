# Import required libraries
import torch
import torchmetrics
import torch.nn as nn
import torch.nn.functional as F

# TODO: Write the captioning loss and image concept predictor loss
class CaptioningLoss(nn.Module):

    def __init__(self, temperature = 0.7):
        super(CaptioningLoss, self).__init__()
        
        self.temperature = temperature

    def forward(self, all_probability_distributions):
        all_probability_distributions = nn.Softmax(dim = 2)(all_probability_distributions)
        return (-torch.sum(all_probability_distributions))