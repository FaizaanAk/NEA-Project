import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
import numpy as np
from typing import Dict, List, Tuple
import re
import os
import json
import random
from difflib import SequenceMatcher

class AnswerEmbeddingNetwork(nn.Module):
    def __init__(self, embedding_dim=768, hidden_dim=512):
        super().__init__()
        # Simpler architecture similar to QuizNeuralNetwork
        self.layer1 = nn.Linear(embedding_dim, hidden_dim)
        self.layer2 = nn.Linear(hidden_dim, hidden_dim)
        self.layer3 = nn.Linear(hidden_dim, embedding_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
        self.similarity = nn.CosineSimilarity(dim=1)
        
    def forward(self, x1, x2=None):
        # Process first input
        x1 = self.relu(self.layer1(x1))
        x1 = self.dropout(x1)
        x1 = self.relu(self.layer2(x1))
        x1 = self.dropout(x1)
        x1 = self.layer3(x1)
        
        if x2 is not None:
            # Process second input
            x2 = self.relu(self.layer1(x2))
            x2 = self.dropout(x2)
            x2 = self.relu(self.layer2(x2))
            x2 = self.dropout(x2)
            x2 = self.layer3(x2)
            
            # Calculate similarity
            similarity = self.similarity(x1, x2)
            return similarity, x1, x2
        
        return x1

class AnswerCheckerAI:
    def __init__(self, model_path='answer_checker_model.pt'):
        # Set device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        try:
            # Initialise BERT
            self.tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')
            self.bert_model = AutoModel.from_pretrained('bert-base-uncased').to(self.device)
            
            # Initialise our network
            self.answer_network = AnswerEmbeddingNetwork().to(self.device)
            
            # Training components
            self.optimizer = torch.optim.AdamW(self.answer_network.parameters(), lr=2e-5)
            self.criterion = nn.MSELoss()
            
            # Load trained model if exists
            self.model_path = model_path
            if os.path.exists(model_path):
                try:
                    checkpoint = torch.load(model_path, map_location=self.device)
                    self.answer_network.load_state_dict(checkpoint['model_state_dict'])
                    self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
                    print(f"Model loaded from {model_path}")
                except Exception as e:
                    print(f"Error loading model: {e}")
            
            # Training data
            self.training_examples = []
            self.best_loss = float('inf')
            
            # Load training data if exists
            if os.path.exists('training_data.json'):
                try:
                    with open('training_data.json', 'r') as f:
                        self.training_examples = json.load(f)
                except Exception as e:
                    print(f"Error loading training data: {e}")
            
            # Enhanced answer templates with simpler variations
            self.answer_templates = {
                'economic_problem': {
                    'question': "Define the economic problem and provide an example?",
                    'answer': "The economic problem refers to the issue of scarcity: society has limited resources but unlimited wants and needs. This requires making choices about how to allocate these scarce resources. For example, a government must decide how to allocate its limited budget between healthcare, education, defence, and other public services.",
                    'variations': [
                        "Scarcity of resources with unlimited wants and needs requiring choices.",
                        "Limited resources must be allocated among unlimited wants.",
                        "How to allocate scarce resources to satisfy unlimited wants."
                    ]
                },
                'economics_social_science': {
                    'question': "What is meant by 'economics as a social science'?",
                    'answer': "Economics as a social science studies human behaviour in relation to how limited resources are allocated to meet unlimited wants and needs in society. It analyses individuals, businesses, governments, and entire economies to understand decision-making patterns and their consequences on society.",
                    'variations': [
                        "Economics studies how people and societies use scarce resources.",
                        "A discipline that examines human behaviour and social interactions regarding resource allocation.",
                        "The study of how societies manage their limited resources to satisfy needs."
                    ]
                },
                'opportunity_cost': {
                    'question': "Define opportunity cost and provide an example.",
                    'answer': "Opportunity cost refers to the value of the next best alternative that is forgone when making a decision. For example, if a student spends time studying for an economics exam instead of going to a concert, the opportunity cost is the enjoyment and experience they would have gained from attending the concert.",
                    'variations': [
                        "The next best alternative that is given up when making a choice.",
                        "What you sacrifice when choosing one option over another.",
                        "The value of what you give up to get something else."
                    ]
                },
                'price_elasticity': {
                    'question': "What is meant by 'price elasticity of demand'? How is it calculated?",
                    'answer': "Price elasticity of demand (PED) measures how responsive quantity demanded is to a change in price. It is calculated as the percentage change in quantity demanded divided by the percentage change in price.",
                    'variations': [
                        "How much demand changes when price changes.",
                        "The responsiveness of buyers to price changes.",
                        "PED shows if demand is sensitive to price changes."
                    ]
                },
                'demand_curve_changes': {
                    'question': "Explain the difference between a movement along the demand curve and a shift of the demand curve.",
                    'answer': "A movement along the demand curve occurs due to a change in the price of the good itself, leading to a change in quantity demanded. In contrast, a shift of the demand curve happens when there is a change in non-price factors (e.g., consumer income, preferences), causing the entire demand curve to move left or right.",
                    'variations': [
                        "Movement is from price changes, shift is from other factors.",
                        "Price changes cause movement along curve, other factors cause shifts.",
                        "When price changes - move along curve. When income or preferences change - shift curve."
                    ]
                },
                'supply': {
                    'question': "Define supply in economics.",
                    'answer': "Supply refers to the quantity of a good or service that producers are willing and able to offer for sale at various price levels in a given time period.",
                    'variations': [
                        "How much producers will sell at different prices.",
                        "What businesses are willing to sell at each price.",
                        "The amount sellers offer at different prices."
                    ]
                },
                'demand': {
                    'question': "What is demand in economics?",
                    'answer': "Demand refers to the quantity of a good or service that consumers are willing and able to purchase at various price levels in a given time period.",
                    'variations': [
                        "How much people will buy at different prices.",
                        "What consumers are willing to buy at each price.",
                        "The amount buyers want at different prices."
                    ]
                },
                'inflation': {
                    'question': "Define inflation and its causes.",
                    'answer': "Inflation is a sustained increase in the general price level of goods and services in an economy over a period of time. It can be caused by demand-pull factors (too much money chasing too few goods), cost-push factors (rising production costs), or monetary factors (excessive money supply growth).",
                    'variations': [
                        "Rising prices across the economy.",
                        "When prices go up and money buys less.",
                        "General increase in prices over time."
                    ]
                }
            }
            
            # Add more concept mappings to improve concept extraction
            self.concept_variations = {
                'demand': ['demand', 'demanded', 'buyers', 'consumers', 'purchasing', 'buying', 'want', 'desire'],
                'supply': ['supply', 'supplied', 'sellers', 'producers', 'production', 'making', 'creating', 'offering'],
                'price': ['price', 'cost', 'value', 'worth', 'expense', 'payment', 'charge', 'fee'],
                'elasticity': ['elasticity', 'elastic', 'inelastic', 'responsiveness', 'sensitivity', 'flexible'],
                'market': ['market', 'marketplace', 'trade', 'exchange', 'buying and selling', 'commerce'],
                'equilibrium': ['equilibrium', 'balance', 'stability', 'steady state', 'market clearing'],
                'inflation': ['inflation', 'rising prices', 'price level', 'purchasing power', 'depreciation'],
                'competition': ['competition', 'competitive', 'rivalry', 'competing', 'contest', 'vying'],
                'monopoly': ['monopoly', 'sole supplier', 'single seller', 'market power', 'price maker'],
                'cost': ['cost', 'expense', 'expenditure', 'payment', 'outlay', 'spending'],
                'economics': ['economics', 'economic', 'economy', 'economic science', 'economic theory', 
                              'microeconomics', 'macroeconomics', 'resource allocation', 'scarcity'],
                'social science': ['social science', 'social studies', 'human society', 'human behavior', 
                                 'sociology', 'social research', 'behavioral science', 'human science']
            }
        
        except Exception as e:
            print(f"Error initializing model: {e}")
            raise

    def get_embedding(self, text: str) -> torch.Tensor:
        # Get BERT embedding for a text
        inputs = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=512, padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.bert_model(**inputs)
        return outputs.last_hidden_state.mean(dim=1)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        # Calculate semantic similarity between two texts
        self.answer_network.eval()
        try:
            with torch.no_grad():
                emb1 = self.get_embedding(text1)
                emb2 = self.get_embedding(text2)
                similarity, _, _ = self.answer_network(emb1, emb2)
            
            # Combine neural similarity with direct text similarity for better results
            neural_sim = similarity.item()
            
            # Also calculate text similarity as backup
            text_sim = self.calculate_text_similarity(text1, text2)
            
            # Take the higher of the two similarity scores
            return max(neural_sim, text_sim)
            
        except Exception as e:
            print(f"Error calculating similarity: {e}")
            # Fallback to direct text similarity
            return self.calculate_text_similarity(text1, text2)

    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        # Calculate direct text similarity using a sequence matcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def train_network(self, epochs=10, batch_size=32):
        # Train the neural network
        if not self.training_examples:
            print("No training data available")
            # Generate some synthetic training examples
            self._generate_synthetic_training_data()
        
        print(f"Training with {len(self.training_examples)} examples")
        
        for epoch in range(epochs):
            self.answer_network.train()
            total_loss = 0
            batch_count = 0
            
            # Shuffle training data
            random.shuffle(self.training_examples)
            
            # Process in batches
            for i in range(0, len(self.training_examples), batch_size):
                batch = self.training_examples[i:i + batch_size]
                batch_loss = self._process_batch(batch)
                
                if batch_loss > 0:  # Only count valid batches
                    total_loss += batch_loss
                    batch_count += 1
            
            # Calculate average loss
            avg_loss = total_loss / batch_count if batch_count > 0 else float('inf')
            
            # Save if best model
            if avg_loss < self.best_loss:
                self.best_loss = avg_loss
                self._save_model(epoch, avg_loss)
            
            print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
            
            # Early stopping
            if avg_loss < 0.01:  # Very good performance
                print("Reached excellent performance, stopping early")
                break

    def _generate_synthetic_training_data(self):
        # Generate synthetic training data from existing templates
        print("Generating synthetic training data...")
        
        for key, template in self.answer_templates.items():
            correct_answer = template['answer']
            
            # Add variations as examples with high scores
            for variation in template.get('variations', []):
                self.add_training_example(variation, correct_answer, 0.9)
            
            # Add first sentence as a good answer
            first_sentence = correct_answer.split('.')[0] + '.'
            self.add_training_example(first_sentence, correct_answer, 0.85)
            
            # Add keyword-only answers as partial matches
            keywords = self._extract_key_concepts(correct_answer)
            if keywords:
                keyword_answer = f"{keywords[0]} is important in economics."
                self.add_training_example(keyword_answer, correct_answer, 0.6)
            
            # Add completely unrelated answers as negative examples
            unrelated = "This is completely unrelated to the topic."
            self.add_training_example(unrelated, correct_answer, 0.1)
        
        print(f"Generated {len(self.training_examples)} training examples")

    def _process_batch(self, batch):
        # Process a single batch
        try:
            batch_loss = 0
            self.optimizer.zero_grad()
            
            for item in batch:
                # Get embeddings
                student_emb = self.get_embedding(item['student_answer'])
                correct_emb = self.get_embedding(item['correct_answer'])
                
                # Forward pass
                similarity, _, _ = self.answer_network(student_emb, correct_emb)
                
                # Calculate loss
                target = torch.tensor([item['score']], dtype=torch.float32).to(self.device)
                loss = self.criterion(similarity, target)
                
                # Backward pass
                loss.backward()
                batch_loss += loss.item()
            
            # Update weights
            torch.nn.utils.clip_grad_norm_(self.answer_network.parameters(), max_norm=1.0)
            self.optimizer.step()
            
            return batch_loss / len(batch)
            
        except Exception as e:
            print(f"Error processing batch: {e}")
            return 0

    def _save_model(self, epoch, loss):
        # Save model checkpoint
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.answer_network.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'loss': loss
        }
        torch.save(checkpoint, self.model_path)

    def add_training_example(self, student_answer: str, correct_answer: str, score: float):
        # Add a new training example
        example = {
            'student_answer': student_answer,
            'correct_answer': correct_answer,
            'score': score
        }
        
        self.training_examples.append(example)
        
        # Save training data
        with open('training_data.json', 'w') as f:
            json.dump(self.training_examples, f)

    def check_answer(self, question: Dict, user_answer: str) -> Tuple[bool, str, float]:
        """Check answer with more flexible matching for human-like answers"""
        try:
            # Handle empty answers
            if not user_answer or user_answer.strip() == "":
                return False, "No answer provided.", 0.0
                
            self.answer_network.eval()
            
            # Clean and normalize
            user_answer = self._normalise_text(user_answer)
            correct_answer = self._normalise_text(question['correct_answer'])
            question_text = self._normalise_text(question.get('question', ''))
            
            # Check for exact match first (ignore case, punctuation)
            exact_match = self._check_exact_match(user_answer, correct_answer)
            if exact_match:
                return True, "✓ Correct! Well done!", 1.0
            
            # Check for matching with template variations
            template_match = self._check_template_variations(user_answer, question)
            if template_match:
                return True, "✓ Correct! Well done!", 0.95
            
            # Get key concepts for both answers
            user_concepts = self._extract_key_concepts(user_answer)
            required_concepts = self._extract_key_concepts(correct_answer)
            question_concepts = self._extract_key_concepts(question_text)
            
            # Find the primary concepts (first 1-2 are likely most important)
            primary_concepts = required_concepts[:min(2, len(required_concepts))]
            if question_concepts:
                # Add concepts from question if they're not already in primary concepts
                for concept in question_concepts:
                    if concept not in primary_concepts:
                        primary_concepts.append(concept)
                        if len(primary_concepts) >= 2:
                            break
            
            # Calculate concept coverage with more weight for primary concepts
            matched_concepts = set(user_concepts) & set(required_concepts)
            primary_matched = any(concept in user_concepts for concept in primary_concepts)
            
            # More lenient concept coverage calculation
            concept_coverage = len(matched_concepts) / len(required_concepts) if required_concepts else 0.5
            
            # Boost score if a primary concept is covered
            if primary_matched:
                concept_coverage = max(concept_coverage, 0.7)  # Ensure at least 0.7 if primary concept found
            
            # Calculate semantic similarity
            similarity = self.calculate_similarity(user_answer, correct_answer)
            
            # Check for direct keyword inclusion
            keyword_match = self._check_keyword_match(user_answer, correct_answer)
            
            # Calculate final score with adjusted weights
            final_score = (0.4 * similarity) + (0.4 * concept_coverage) + (0.2 * keyword_match)
            
            # Check for near-exact matches using text similarity
            text_similarity = self.calculate_text_similarity(user_answer, correct_answer)
            if text_similarity > 0.9:  # Very high text similarity
                final_score = max(final_score, 0.95)  # Boost score for very similar answers
            
            # Lower threshold for correctness but maintain high standards
            is_correct = final_score >= 0.70  # Slightly more lenient threshold
            
            # Generate appropriate feedback
            if is_correct:
                feedback = "✓ Correct! Well done!"
            else:
                feedback = "✗ Not quite right."
            
            # Add to training data if the user answer is substantial
            if len(user_answer.split()) > 3:
                training_score = 0.9 if is_correct else max(0.3, final_score)  # More nuanced training scores
                self.add_training_example(user_answer, correct_answer, training_score)
            
            return is_correct, feedback, final_score
        
        except Exception as e:
            print(f"Error checking answer: {e}")
            # Fallback to simple text similarity
            try:
                simple_sim = self.calculate_text_similarity(user_answer, question['correct_answer'])
                is_correct = simple_sim > 0.7  # More lenient fallback threshold
                feedback = "✓ Correct! Well done!" if is_correct else "✗ Not quite right."
                return is_correct, feedback, simple_sim
            except:
                return False, "Error checking answer. Please try again.", 0.0

    def _check_exact_match(self, user_answer: str, correct_answer: str) -> bool:
        """Check for exact match after normalization"""
        # For very short answers, require closer match
        if len(user_answer.split()) <= 5:
            # If user answer is very short, check if it's very similar to part of the correct answer
            similarity = self.calculate_text_similarity(user_answer, correct_answer)
            if similarity > 0.85:  # Slightly more lenient for short answers
                return True
                
            # Also check if it's a subset of the correct answer
            if user_answer in correct_answer:
                return True
            
            # Check if it matches the beginning of the correct answer
            if correct_answer.startswith(user_answer):
                return True
        
        # For longer answers, check if they're semantically equivalent
        similarity = self.calculate_similarity(user_answer, correct_answer)
        text_similarity = self.calculate_text_similarity(user_answer, correct_answer)
        
        # Consider it an exact match if either similarity is very high
        return similarity > 0.9 or text_similarity > 0.9

    def _check_template_variations(self, user_answer: str, question: Dict) -> bool:
        # Check if the user answer matches any template variations
        # Extract relevant templates based on question content
        question_text = self._normalise_text(question['question'])
        
        for key, template in self.answer_templates.items():
            # Check if this template is relevant to the question
            template_question = self._normalise_text(template['question'])
            if self.calculate_text_similarity(question_text, template_question) > 0.7:
                # Check against all variations
                for variation in template.get('variations', []):
                    variation_text = self._normalise_text(variation)
                    if self.calculate_text_similarity(user_answer, variation_text) > 0.7:
                        return True
                        
                # Also check against main answer
                template_answer = self._normalise_text(template['answer'])
                if self.calculate_text_similarity(user_answer, template_answer) > 0.8:
                    return True
        
        return False

    def _check_keyword_match(self, user_answer: str, correct_answer: str) -> float:
        # Calculate a score based on keyword matching
        # Extract key phrases (2-3 word phrases)
        correct_phrases = self._extract_key_phrases(correct_answer)
        
        # Count how many key phrases are in the user answer
        matches = 0
        for phrase in correct_phrases:
            if phrase in user_answer:
                matches += 1
        
        # Calculate match percentage
        if not correct_phrases:
            return 0.5  # Neutral if no phrases found
        return min(1.0, matches / len(correct_phrases))

    def _extract_key_phrases(self, text: str) -> List[str]:
        # Extract key 2-3 word phrases from text
        words = text.split()
        phrases = []
        
        # Generate 2-word phrases
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            phrases.append(phrase)
        
        # Generate 3-word phrases
        for i in range(len(words) - 2):
            phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
            phrases.append(phrase)
            
        return phrases[:10]  # Limit to top 10 phrases

    def evaluate_model(self, num_samples=100):
        # Evaluate model performance
        if not self.training_examples:
            print("No test data available")
            return
        
        # Use random subset of training data for evaluation
        test_data = random.sample(self.training_examples, min(num_samples, len(self.training_examples)))
        
        self.answer_network.eval()
        total_accuracy = 0
        total_examples = len(test_data)
        
        with torch.no_grad():
            for item in test_data:
                similarity = self.calculate_similarity(
                    item['student_answer'],
                    item['correct_answer']
                )
                predicted_score = similarity.item()
                actual_score = item['score']
                
                # Consider prediction correct if within 0.15 of actual score
                if abs(predicted_score - actual_score) < 0.15:
                    total_accuracy += 1
        
        accuracy = total_accuracy / total_examples
        print(f"Model Accuracy: {accuracy:.2%}")
        return accuracy

    def _normalise_text(self, text: str) -> str:
        # Normalise text for comparison
        # Handle None or empty text
        if not text:
            return ""
            
        # Convert to lowercase and strip whitespace
        text = text.lower().strip()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove punctuation that doesn't affect meaning
        text = text.replace(',', ' ').replace(';', ' ').replace(':', ' ')
        
        # Standardise some common terms
        text = text.replace("don't", "do not").replace("doesn't", "does not")
        text = text.replace("can't", "cannot").replace("won't", "will not")
        
        return text

    def _extract_key_concepts(self, text: str) -> List[str]:
        # Extract key economic concepts with more flexibility
        # Original list of concepts
        key_concepts = [
            'demand', 'supply', 'price', 'market', 'elasticity', 'cost',
            'inflation', 'gdp', 'unemployment', 'competition', 'equilibrium',
            'monopoly', 'oligopoly', 'efficiency', 'growth', 'trade',
            'fiscal', 'monetary', 'aggregate', 'investment', 'consumption',
            'externality', 'public good', 'market failure', 'opportunity cost'
        ]
        
        found_concepts = []
        text_lower = text.lower()
        
        # Look for original concepts
        for concept in key_concepts:
            if concept in text_lower:
                found_concepts.append(concept)
        
        # Look for variations using concept_variations mapping
        for concept, variations in self.concept_variations.items():
            for variation in variations:
                if variation in text_lower and concept not in found_concepts:
                    found_concepts.append(concept)
        
        return found_concepts

    def _generate_feedback(self, is_correct: bool, user_answer: str, 
                         correct_answer: str, matched_concepts: set,
                         required_concepts: List[str]) -> str:
        # Generate feedback based on the answer assessment
        if is_correct:
            return "✓ Correct! Well done!"
        
        # Create feedback for incorrect answers
        feedback = ["✗ Not quite right."]
        
        # Add the correct answer
        feedback.append("\nCorrect answer:")
        feedback.append(correct_answer)
        
        return "\n".join(feedback)

    def get_model_answer(self, question_text: str) -> str:
        # Get the model answer for a question with improved matching
        if not question_text:
            return None
            
        question_text = self._normalise_text(question_text)
        
        # First try direct keyword matching for specific economic concepts
        key_terms = [
            ("economic problem", "economic_problem"),
            ("opportunity cost", "opportunity_cost"),
            ("economics as a social science", "economics_social_science"),
            ("price elasticity", "price_elasticity"),
            ("demand curve", "demand_curve_changes"),
            ("supply", "supply"),
            ("demand", "demand"),
            ("inflation", "inflation")
        ]
        
        # Check for direct keyword matches first
        for term, template_key in key_terms:
            if term in question_text and template_key in self.answer_templates:
                return self.answer_templates[template_key]['answer']
        
        # Then try more sophisticated matching
        best_match = None
        highest_similarity = 0.5  # Minimum threshold for a match
        
        for key, template in self.answer_templates.items():
            template_question = self._normalise_text(template['question'])
            # Calculate similarity between the template question and the input question
            similarity = self.calculate_text_similarity(question_text, template_question)
            
            # Extract keywords from both questions
            question_words = set(question_text.split())
            template_words = set(template_question.split())
            common_words = question_words.intersection(template_words)
            
            # Adjust similarity based on common words
            word_match_boost = len(common_words) / max(len(question_words), 1) * 0.2
            adjusted_similarity = similarity + word_match_boost
            
            if adjusted_similarity > highest_similarity:
                highest_similarity = adjusted_similarity
                best_match = template
        
        if best_match:
            return best_match['answer']
        
        return None

    def update_answer_template(self, question: str, answer: str, variations: List[str] = None) -> None:
        # Add or update an answer template with variations
        key = re.sub(r'[^a-z0-9]', '_', self._normalise_text(question))
        
        # Create template entry
        template = {
            'question': question,
            'answer': answer
        }
        
        # Add variations if provided
        if variations:
            template['variations'] = variations
        
        # Update templates
        self.answer_templates[key] = template 