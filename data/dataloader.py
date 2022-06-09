# TODO: Implement two dataloading classes
#   1. ImageCaptionDataset
#   2. VQADataset

# Import the required libraries
import os
import json
from sre_parse import Tokenizer
from data.preprocess_data import preprocess
import torch
import warnings
import regex as re
from tqdm import tqdm
from PIL import Image
from torchvision import transforms
from torch.utils.data import Dataset, DataLoader, TensorDataset
import numpy as np
from copy import deepcopy

from torchtext.data.utils import get_tokenizer
import torch.nn.functional as F

# TODO: Update the code for word representation into one hot form
# Image Caption Dataset for coco, flickr30k, flickr8k

class ImageCaptionDataset(Dataset):

	def __init__(self, dataset, preprocess_text = True, split = "train", max_length_caption = 64,
				image_resize = (224, 224), warn_grayscale = False, eval = False):

		self.dataset = dataset
		self.preprocess_text = preprocess_text
		self.split = split
		self.max_length_caption = max_length_caption
		self.image_resize = image_resize
		self.warn_grayscale = warn_grayscale
		
		self.transform = transforms.Compose([transforms.Resize(self.image_resize), transforms.ToTensor()])

		self.tokenizer = get_tokenizer("basic_english")
		self.preprocessed_dict = json.load(open(f'./datasets/{self.dataset}/{self.split}_image_captions.json', 'r'))
		self.vocabulary = torch.load(f'./datasets/{self.dataset}/train_vocabulary.pth')
		self.concept_vocabulary = torch.load(f'./datasets/{self.dataset}/all_concept_vocabulary.pth')

		self.num_concepts = len(self.concept_vocabulary)

		self.image_ids = []
		self.image_paths = []
		self.captions = []
		self.preprocessed_captions = []

		for image_id, path_caption_dict in self.preprocessed_dict.items():
			
			if eval:
				num_captions = 1
			else:
				num_captions = len(path_caption_dict["captions"])

			image_path = path_caption_dict["image_path"]

			self.image_ids.extend([image_id] * num_captions)   
			self.image_paths.extend([image_path] * num_captions)
			captions = path_caption_dict['captions'][:num_captions]

			for idx in range(num_captions):
				if self.preprocess_text:
					captions[idx] = self.preprocess_caption(captions[idx])

			self.preprocessed_captions.extend(deepcopy(captions))

	def __len__(self):
		return len(self.image_ids)

	def __getitem__(self, idx):

		image_path = self.image_paths[idx]
		image = Image.open(image_path)

		# Convert gray scale image to RGB
		if image.mode == 'L':
			if self.warn_grayscale:
				warnings.warn('image %s is grayscale..' % image_path,
							RuntimeWarning)
			image = image.convert('RGB')
		
		image = self.transform(image)

		caption = self.preprocessed_captions[idx]
		tokenized_caption = self.tokenizer(caption)

		word_embeddings = self.get_one_hot_word_vector(tokenized_caption, self.max_length_caption)
		ground_concept_vector = self.get_concept_vector(tokenized_caption)

		return image, word_embeddings, ground_concept_vector

	# def get_one_hot_word_vector(self, words, keys: Union[str, Iterable], max_length):
	def get_one_hot_word_vector(self, words, max_length):
		
		if isinstance(words, str):
			words = [words]
		
		one_hot = F.one_hot(torch.tensor(self.vocabulary.lookup_indices(words)), num_classes = len(self.vocabulary))
		if one_hot.size()[0] > max_length:
			one_hot = one_hot[:max_length, :]
		elif one_hot.size()[0] < max_length:
			padding = torch.zeros((max_length - one_hot.size()[0], one_hot.size()[1]))
			one_hot = torch.cat([one_hot, padding], dim = 0)

		return one_hot

	def get_concept_vector(self, words):

		concept_vector = torch.zeros((self.num_concepts, 1))
		for word in words:
			if self.concept_vocabulary.lookup_indices(word):
				concept_vector[self.concept_vocabulary.lookup_indices(word)] = 1

		return concept_vector

	def collater(self, items):

		batch = {"image": torch.stack([x[0] for x in items], dim = 0),
				"word_embeddings": torch.stack([x[1] for x in items], dim = 0),
				"ground_concept_vector": torch.stack([x[2] for x in items], dim = 0)}
		return batch

	def preprocess_caption(self, caption):

		caption = re.sub('[^a-zA-Z0-9.?,]', ' ', caption)
			
		url = re.compile(r'https?://\S+|www\.\S+')
		caption = url.sub(r'', caption)
		
		html = re.compile(r'<.*?>')
		caption = html.sub(r'', caption)

		emoji_pattern = re.compile("["
								u"\U0001F600-\U0001F64F"  # emoticons
								u"\U0001F300-\U0001F5FF"  # symbols & pictographs
								u"\U0001F680-\U0001F6FF"  # transport & map symbols
								u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
								u"\U00002702-\U000027B0"
								u"\U000024C2-\U0001F251"
								"]+", flags=re.UNICODE)
		caption = emoji_pattern.sub(r'', caption)

		return caption

class VisualQuestionAnsweringDataset(Dataset):

	def __init__(self, dataset, preprocess_text = True, split = "train", max_length_caption = 64,
				image_resize = (224, 224), warn_grayscale = False, eval = False):

		self.dataset = dataset
		self.preprocess_text = preprocess_text
		self.split = split
		self.max_length_caption = max_length_caption
		self.image_resize = image_resize
		self.warn_grayscale = warn_grayscale
		
		self.transform = transforms.Compose([transforms.Resize(self.image_resize), transforms.ToTensor()])

		self.tokenizer = get_tokenizer("basic_english")
		self.preprocessed_dict = json.load(open(f'./datasets/{self.dataset}/{self.split}_image_captions.json', 'r'))
		self.vocabulary = torch.load(f'./datasets/{self.dataset}/train_vocabulary.pth')
		self.concept_vocabulary = torch.load(f'./datasets/{self.dataset}/all_concept_vocabulary.pth')

		self.num_concepts = len(self.concept_vocabulary)

		self.image_ids = []
		self.image_paths = []
		self.captions = []
		self.preprocessed_captions = []
		self.questions = []
		self.answers = []

		for image_id, path_caption_dict in self.preprocessed_dict.items():
			
			if eval:
				num_captions = 1
			else:
				num_captions = len(path_caption_dict["captions"])

			image_path = path_caption_dict["image_path"]
			question = path_caption_dict["question"]
			answer = path_caption_dict["answer"]

			self.image_ids.extend([image_id] * num_captions)   
			self.image_paths.extend([image_path] * num_captions)
			self.questions.extend([question] * num_captions)
			self.answers.extend([answer] * num_captions)

			captions = path_caption_dict['captions'][:num_captions]

			for idx in range(num_captions):
				if self.preprocess_text:
					captions[idx] = self.preprocess_caption(captions[idx])

			self.preprocessed_captions.extend(deepcopy(captions))

	def __len__(self):
		return len(self.image_ids)

	def __getitem__(self, idx):

		image_path = self.image_paths[idx]
		image = Image.open(image_path)

		# Convert gray scale image to RGB
		if image.mode == 'L':
			if self.warn_grayscale:
				warnings.warn('image %s is grayscale..' % image_path,
							RuntimeWarning)
			image = image.convert('RGB')
		
		image = self.transform(image)

		caption = self.preprocessed_captions[idx]
		tokenized_caption = self.tokenizer(caption)

		word_embeddings = self.get_one_hot_word_vector(tokenized_caption, self.max_length_caption)
		ground_concept_vector = self.get_concept_vector(tokenized_caption)

		question = self.questions[idx]
		tokenized_question = self.tokenizer(question)
		question_embeddings = self.get_one_hot_word_vector(tokenized_question, self.max_length_caption)

		answer = self.answers[idx]

		return image, word_embeddings, ground_concept_vector, question_embeddings, answer

	# def get_one_hot_word_vector(self, words, keys: Union[str, Iterable], max_length):
	def get_one_hot_word_vector(self, words, max_length):
		
		if isinstance(words, str):
			words = [words]
		
		one_hot = F.one_hot(torch.tensor(self.vocabulary.lookup_indices(words)), num_classes = len(self.vocabulary))
		if one_hot.size()[0] > max_length:
			one_hot = one_hot[:max_length, :]
		elif one_hot.size()[0] < max_length:
			padding = torch.zeros((max_length - one_hot.size()[0], one_hot.size()[1]))
			one_hot = torch.cat([one_hot, padding], dim = 0)

		return one_hot

	def get_concept_vector(self, words):

		concept_vector = torch.zeros((self.num_concepts, 1))
		for word in words:
			if self.concept_vocabulary.lookup_indices(word):
				concept_vector[self.concept_vocabulary.lookup_indices(word)] = 1

		return concept_vector

	def collater(self, items):

		batch = {"image": torch.stack([x[0] for x in items], dim = 0),
				"word_embeddings": torch.stack([x[1] for x in items], dim = 0),
				"ground_concept_vector": torch.stack([x[2] for x in items], dim = 0),
				"question_embeddings": torch.stack([x[3] for x in items], dim = 0),
				"answer": torch.stack([x[4] for x in items], dim = 0)}
		return batch

	def preprocess_caption(self, caption):

		caption = re.sub('[^a-zA-Z0-9.?,]', ' ', caption)
			
		url = re.compile(r'https?://\S+|www\.\S+')
		caption = url.sub(r'', caption)
		
		html = re.compile(r'<.*?>')
		caption = html.sub(r'', caption)

		emoji_pattern = re.compile("["
								u"\U0001F600-\U0001F64F"  # emoticons
								u"\U0001F300-\U0001F5FF"  # symbols & pictographs
								u"\U0001F680-\U0001F6FF"  # transport & map symbols
								u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
								u"\U00002702-\U000027B0"
								u"\U000024C2-\U0001F251"
								"]+", flags=re.UNICODE)
		caption = emoji_pattern.sub(r'', caption)

		return caption