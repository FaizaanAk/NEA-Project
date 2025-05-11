import random
import numpy as np
import torch
import torch.nn as nn
from notes import get_notes_content
from flashcards import get_flashcards_content
import os
import re
from difflib import SequenceMatcher

class QuizNeuralNetwork(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super(QuizNeuralNetwork, self).__init__()
        self.layer1 = nn.Linear(input_size, hidden_size)
        self.layer2 = nn.Linear(hidden_size, hidden_size)
        self.layer3 = nn.Linear(hidden_size, output_size)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, x):
        x = self.relu(self.layer1(x))
        x = self.dropout(x)
        x = self.relu(self.layer2(x))
        x = self.dropout(x)
        x = self.layer3(x)
        return x

class QuizGenerator:
    def __init__(self):
        self.notes = get_notes_content()
        self.flashcards = get_flashcards_content()
        self.used_questions = set()
        
        # Define question templates for different types of questions
        self.question_templates = {
            'definition': [
                "Define {concept} and provide an example.",
                "What is meant by '{concept}'?",
                "Explain what is meant by the term '{concept}'.",
                "What do economists mean by '{concept}'?",
                "Define '{concept}' in economic terms."
            ],
            'explanation': [
                "Explain the concept of '{concept}' in economics.",
                "Describe how {concept} works in practice.",
                "Explain the difference between {concept1} and {concept2}.",
                "What is the relationship between {concept1} and {concept2}?",
                "How does {concept} affect economic behaviour?"
            ],
            'analysis': [
                "Analyse the impact of {concept} on {context}.",
                "Evaluate the effectiveness of {concept} in {context}.",
                "Discuss the advantages and disadvantages of {concept}.",
                "What factors influence {concept}?",
                "How might changes in {concept} affect {context}?"
            ],
            'application': [
                "Using an example, demonstrate how {concept} operates in practice.",
                "Describe two factors that can cause {concept}.",
                "Explain how {concept} is measured.",
                "What are the main characteristics of {concept}?",
                "How might a business use {concept} in decision-making?"
            ],
            'comparison': [
                "Compare and contrast {concept1} and {concept2}.",
                "What is the difference between {concept1} and {concept2}?",
                "Distinguish between {concept1} and {concept2}.",
                "How does {concept1} differ from {concept2}?",
                "Explain the key differences between {concept1} and {concept2}."
            ]
        }
        
        # Comprehensive mapping of subtopics to their specific concepts
        self.subtopic_concepts = {
            'supply': [
                'supply', 'supply curve', 'quantity supplied', 'aggregate supply', 
                'SRAS', 'LRAS', 'supply side', 'producer', 'production', 'cost of production',
                'marginal cost', 'supply elasticity', 'production capacity', 'producer surplus',
                'supply shock', 'factors of production', 'production process', 'supply function'
            ],
            'demand': [
                'demand', 'demand curve', 'quantity demanded', 'aggregate demand', 
                'AD', 'derived demand', 'consumer', 'consumption', 'willingness to pay',
                'buyer', 'demand elasticity', 'consumer surplus', 'demand function',
                'demand shock', 'preferences', 'utility', 'diminishing marginal utility'
            ],
            'elasticity': [
                'elasticity', 'price elasticity', 'income elasticity', 'cross elasticity',
                'elastic', 'inelastic', 'unit elastic', 'PED', 'YED', 'XED',
                'elasticity coefficient', 'elasticity formula', 'price sensitivity'
            ],
            'market': [
                'market', 'market structure', 'market failure', 'perfect market',
                'free market', 'command economy', 'mixed economy', 'market equilibrium',
                'market clearing', 'invisible hand', 'competitive market', 'market forces'
            ],
            'price': [
                'price', 'market price', 'equilibrium price', 'relative price',
                'price mechanism', 'price discrimination', 'price taker', 'price maker',
                'price floor', 'price ceiling', 'price controls', 'price stability'
            ],
            'competition': [
                'competition', 'perfect competition', 'monopolistic competition',
                'oligopoly', 'monopoly', 'contestable markets', 'barriers to entry',
                'competitive advantage', 'imperfect competition', 'market power'
            ],
            'efficiency': [
                'efficiency', 'allocative efficiency', 'productive efficiency',
                'economic efficiency', 'dynamic efficiency', 'x-inefficiency',
                'pareto efficiency', 'deadweight loss', 'welfare loss'
            ],
            'costs': [
                'cost', 'opportunity cost', 'marginal cost', 'average cost',
                'fixed cost', 'variable cost', 'total cost', 'sunk cost',
                'economic cost', 'accounting cost', 'cost curve', 'cost function'
            ],
            'revenue': [
                'revenue', 'total revenue', 'marginal revenue', 'average revenue',
                'revenue maximization', 'sales revenue', 'profit', 'loss',
                'break-even', 'revenue curve'
            ],
            'inflation': [
                'inflation', 'price level', 'deflation', 'hyperinflation',
                'cost-push', 'demand-pull', 'disinflation', 'CPI', 'RPI',
                'inflation rate', 'purchasing power', 'real value', 'nominal value'
            ],
            'unemployment': [
                'unemployment', 'cyclical unemployment', 'structural unemployment',
                'frictional unemployment', 'seasonal unemployment', 'natural rate',
                'real wage unemployment', 'labor market', 'jobless', 'unemployment rate'
            ]
        }

    def _format_question(self, question_text):
        # Format questions to be clear and concise
        # Clean and normalise the question text
        question_text = question_text.strip()
        question_text = question_text[0].upper() + question_text[1:].lower()
        
        # Ensure question ends with appropriate punctuation
        if not question_text.endswith('?'):
            question_text = question_text.rstrip('.') + '?'
        
        return question_text

    def _format_answer(self, answer):
        # Format answers to be clear and concise with simpler language
        # Clean the answer text
        answer = answer.strip()
        answer = ' '.join(answer.split())
        
        # Simplify language (remove complex academic phrases)
        answer = re.sub(r'in accordance with', 'following', answer)
        answer = re.sub(r'aforementioned', 'mentioned', answer)
        answer = re.sub(r'consequently', 'so', answer)
        answer = re.sub(r'furthermore', 'also', answer)
        answer = re.sub(r'nevertheless', 'however', answer)
        
        # Capitalize first letter
        if answer and answer[0].islower():
            answer = answer[0].upper() + answer[1:]
        
        # Ensure proper punctuation
        if not answer.endswith(('.', '!', '?')):
            answer += '.'
        
        # Shorten answer if it's too long (focus on key points)
        if len(answer.split()) > 50:
            sentences = answer.split('.')
            answer = '. '.join(sentences[:3]) + '.'
        
        return answer

    def _create_question_from_flashcards(self, content, subtopic):
        # Create questions from flashcards ensuring they match the subtopic
        # Skip if this question was already used
        temp_question = {
            'question': content['question'].strip(),
            'correct_answer': content['answer'].strip()
        }
        if self._is_question_used(temp_question):
            return None
        
        # Verify the flashcard is relevant to the subtopic
        question_text = content['question'].strip().lower()
        answer_text = content['answer'].strip().lower()
        
        # Check if question or answer contains the subtopic name or related concepts
        is_relevant = False
        if subtopic.lower() in question_text or subtopic.lower() in answer_text:
            is_relevant = True
        else:
            # Check for subtopic-specific concepts
            relevant_concepts = self.subtopic_concepts.get(subtopic.lower(), [])
            for concept in relevant_concepts:
                if concept in question_text or concept in answer_text:
                    is_relevant = True
                    break
        
        if not is_relevant:
            return None
        
        # Format the question and answer
        formatted_answer = self._format_answer(content['answer'])
        
        # Create question
        question = {
            'type': 'open_ended',
            'question': self._format_question(content['question']),
            'correct_answer': formatted_answer,
            'topic': content['topic']
        }

        # Mark question as used
        self._mark_question_used(question)
        return question

    def _create_question_from_notes(self, content, subtopic):
        # Create questions from notes content using templates and actual content
        if not content.get('text'):
            return None
            
        # Extract section title, heading and text
        section_title = content.get('title', '')
        section_heading = content.get('heading', '')
        section_text = content.get('text', '')
        
        # Split text into bullet points if present
        bullet_points = []
        if '•' in section_text:
            bullet_points = [point.strip() for point in section_text.split('•') if point.strip()]
        elif '\n-' in section_text:  # Handle dash-style bullet points
            bullet_points = [point.strip() for point in section_text.split('\n-') if point.strip()]
        
        # Generate different types of questions based on content
        question_types = []
        
        # Type 1: Definition/Explanation questions from title
        if section_title and section_text:
            # Extract relevant part of text that defines or explains the title
            definition_text = section_text
            if bullet_points:
                # Use first 2-3 relevant bullet points for the definition
                relevant_points = []
                for point in bullet_points[:3]:
                    if section_title.lower() in point.lower() or any(keyword in point.lower() for keyword in section_title.lower().split()):
                        relevant_points.append(point)
                if relevant_points:
                    definition_text = ' '.join(relevant_points)
            
            # Create contextual definition question
            if section_heading:
                # If we have a heading, use it for context
                question_text = f"In the context of {section_heading}, what is meant by {section_title}?"
            else:
                # Use subtopic for context
                question_text = f"In {subtopic}, what is meant by {section_title}?"
            
            question_data = {
                'type': 'definition',
                'question': question_text,
                'answer': self._construct_answer(definition_text, section_title)
            }
            
            if not self._is_question_used(question_data):
                question_types.append(question_data)
        
        # Type 2: Questions from bullet points
        if bullet_points:
            for point in bullet_points:
                if ':' in point:
                    concept, explanation = point.split(':', 1)
                    # Only create question if explanation is substantial
                    if len(explanation.strip().split()) >= 5:
                        # Create contextual questions
                        context = section_heading if section_heading else section_title if section_title else subtopic
                        question_formats = [
                            f"Within {context}, explain the role of {concept.strip()}.",
                            f"In relation to {context}, what is meant by {concept.strip()}?",
                            f"How does {concept.strip()} contribute to {context}?"
                        ]
                        question_text = random.choice(question_formats)
                        question_data = {
                            'type': 'explanation',
                            'question': question_text,
                            'answer': self._construct_answer(explanation.strip(), concept.strip())
                        }
                        if not self._is_question_used(question_data):
                            question_types.append(question_data)
                elif '-' in point and not point.startswith('-'):  # Avoid bullet points that are just lists
                    concept, explanation = point.split('-', 1)
                    if len(explanation.strip().split()) >= 5:
                        context = section_heading if section_heading else section_title if section_title else subtopic
                        question_data = {
                            'type': 'explanation',
                            'question': f"In the context of {context}, describe what is meant by {concept.strip()}.",
                            'answer': self._construct_answer(explanation.strip(), concept.strip())
                        }
                        if not self._is_question_used(question_data):
                            question_types.append(question_data)
        
        # Type 3: Comparison questions if multiple concepts present
        if len(bullet_points) >= 2:
            # Find pairs of related points to compare
            for i in range(len(bullet_points) - 1):
                point1 = bullet_points[i]
                point2 = bullet_points[i + 1]
                
                # Extract concepts and explanations
                concept1 = point1.split(':')[0].strip() if ':' in point1 else point1.split('-')[0].strip() if '-' in point1 else point1
                concept2 = point2.split(':')[0].strip() if ':' in point2 else point2.split('-')[0].strip() if '-' in point2 else point2
                
                # Only create comparison if concepts are different but related
                if concept1 != concept2 and self._are_concepts_related(concept1, concept2):
                    answer = self._construct_comparison_answer(point1, point2)
                    if answer:
                        context = section_heading if section_heading else section_title if section_title else subtopic
                        comparison_formats = [
                            f"Within {context}, compare and contrast {concept1} and {concept2}.",
                            f"In the context of {context}, what are the key differences between {concept1} and {concept2}?",
                            f"How do {concept1} and {concept2} differ in their roles within {context}?"
                        ]
                        question_text = random.choice(comparison_formats)
                        question_data = {
                            'type': 'comparison',
                            'question': question_text,
                            'answer': answer
                        }
                        if not self._is_question_used(question_data):
                            question_types.append(question_data)
        
        # Type 4: Application questions from content
        if section_text and ('example' in section_text.lower() or 'such as' in section_text.lower()):
            # Extract example from text
            example_text = self._extract_example(section_text)
            if example_text:
                context = section_heading if section_heading else section_title if section_title else subtopic
                application_formats = [
                    f"Using an example, demonstrate how {section_title} is applied in {context}.",
                    f"Provide a practical example of how {section_title} works in {context}.",
                    f"In the context of {context}, how is {section_title} applied in practice?"
                ]
                question_text = random.choice(application_formats)
                question_data = {
                    'type': 'application',
            'question': question_text,
                    'answer': self._construct_example_answer(example_text, section_title)
                }
                if not self._is_question_used(question_data):
                    question_types.append(question_data)
        
        # Select a random question type if multiple available
        if not question_types:
            return None
        
        question_data = random.choice(question_types)
        
        # Format question and answer
        question = {
            'type': 'open_ended',
            'question': self._format_question(question_data['question']),
            'correct_answer': self._format_answer(question_data['answer']),
            'topic': subtopic
        }

        # Mark question as used
        self._mark_question_used(question_data)
        return question

    def _construct_answer(self, text, concept):
        """Construct a clear, focused answer about a concept using the provided text."""
        # Clean up the text
        text = text.strip()
        
        # If text is a list of points, combine them
        if isinstance(text, list):
            text = ' '.join(text)
        
        # Remove any bullet points or dashes at the start
        text = re.sub(r'^[•\-]\s*', '', text)
        
        # If the concept isn't mentioned in the answer, add it
        if concept.lower() not in text.lower():
            text = f"{concept} refers to {text}"
        
        # Add examples if present in original text
        examples = re.findall(r'(?:example[s]?:?|such as|e\.g\.,)(.*?)(?:\.|$)', text, re.I)
        if examples:
            example_text = examples[0].strip()
            if example_text and example_text not in text:
                text = f"{text} For example, {example_text}."
        
        return text

    def _construct_comparison_answer(self, point1, point2):
        """Construct a comparison answer from two points."""
        # Extract content from points
        content1 = point1.split(':', 1)[1].strip() if ':' in point1 else point1.split('-', 1)[1].strip() if '-' in point1 else point1
        content2 = point2.split(':', 1)[1].strip() if ':' in point2 else point2.split('-', 1)[1].strip() if '-' in point2 else point2
        
        # Only proceed if both points have substantial content
        if len(content1.split()) < 3 or len(content2.split()) < 3:
            return None
        
        return f"{content1} In contrast, {content2}"

    def _construct_example_answer(self, example_text, concept):
        """Construct an answer that focuses on practical examples."""
        # Clean up the example text
        example_text = example_text.strip()
        
        # If no specific example found, return None
        if not example_text:
            return None
        
        # Format the answer to clearly link the example to the concept
        return f"{concept} can be demonstrated through the following example: {example_text}"

    def _extract_example(self, text):
        """Extract example from text."""
        # Look for examples after various markers
        markers = ['example:', 'examples:', 'such as', 'e.g.,', 'for example']
        
        for marker in markers:
            if marker in text.lower():
                # Find the example part
                parts = text.lower().split(marker)
                if len(parts) > 1:
                    example = parts[1].split('.')[0].strip()
                    if example:
                        return example
        
        return None

    def _are_concepts_related(self, concept1, concept2):
        """Check if two concepts are related enough to compare."""
        # Convert concepts to lowercase for comparison
        c1 = concept1.lower()
        c2 = concept2.lower()
        
        # Check if concepts share common words
        words1 = set(c1.split())
        words2 = set(c2.split())
        common_words = words1.intersection(words2)
        
        # If they share words, they're related
        if common_words:
            return True
        
        # Check if they're in the same concept group
        for group in self.subtopic_concepts.values():
            if c1 in [g.lower() for g in group] and c2 in [g.lower() for g in group]:
                return True
        
        return False

    def _extract_general_concepts(self, text):
        # Extract general economic concepts from text (fallback method)
        # List of common economic concepts
        general_concepts = [
            'supply', 'demand', 'price', 'market', 'elasticity', 'cost',
            'inflation', 'gdp', 'unemployment', 'competition', 'equilibrium',
            'monopoly', 'oligopoly', 'efficiency', 'growth', 'trade',
            'fiscal', 'monetary', 'aggregate', 'investment', 'consumption'
        ]
        
        found_concepts = []
        text_lower = text.lower()
        for concept in general_concepts:
            if concept in text_lower:
                found_concepts.append(concept)
                
        return found_concepts

    def _extract_key_concepts(self, text, subtopic):
        # Extract key economic concepts from text that are relevant to the subtopic
        # Get concepts specific to this subtopic
        relevant_concepts = self.subtopic_concepts.get(subtopic.lower(), [])
        if not relevant_concepts:  # If subtopic not in mapping, use general approach
            return self._extract_general_concepts(text)
        
        # Look for subtopic-specific concepts
        found_concepts = []
        text_lower = text.lower()
        for concept in relevant_concepts:
            if concept in text_lower:
                found_concepts.append(concept)
        
        # If no specific concepts found, check if subtopic name itself is in text
        if not found_concepts and subtopic.lower() in text_lower:
            found_concepts.append(subtopic)
        
        return found_concepts

    def _extract_answer_from_content(self, content, concept):
        # Extract relevant answer from content based on concept
        text = content['text']
        sentences = text.split('.')
        
        # Look for sentences containing the concept
        relevant_sentences = []
        for sentence in sentences:
            if concept.lower() in sentence.lower():
                relevant_sentences.append(sentence.strip())
        
        # If found relevant sentences, combine them
        if relevant_sentences:
            # Limit to 3 sentences maximum for clarity
            return ' '.join(relevant_sentences[:3])
        
        # If no specific sentences found, return first two sentences as general context
        return ' '.join(sentences[:2]).strip()

    def _generate_question_hash(self, question):
        # Generate a unique hash for a question
        # Handle both dictionary formats (old and new)
        if isinstance(question, dict):
            if 'type' in question:
                # New format with type field
                return hash(f"{question.get('question', '')}_{question.get('answer', '')}")
            else:
                # Old format
                return hash(f"{question.get('question', '')}_{question.get('correct_answer', '')}")
        return hash(str(question))  # Fallback for unexpected formats

    def _is_question_used(self, question):
        # Check if a question has been used before
        try:
            question_hash = self._generate_question_hash(question)
            return question_hash in self.used_questions
        except Exception as e:
            print(f"Warning: Error checking question usage: {e}")
            return False  # If there's an error, assume question is not used

    def _mark_question_used(self, question):
        # Mark a question as used
        try:
            question_hash = self._generate_question_hash(question)
            self.used_questions.add(question_hash)
        except Exception as e:
            print(f"Warning: Error marking question as used: {e}")

    def generate_quiz_for_subtopic(self, topic_id, subtopic, num_questions=5):
        """Generate a quiz specific to a subtopic with better content utilization"""
        quiz = []
        self.used_questions.clear()
        
        # Get content specific to this subtopic
        notes_content = self._extract_content_from_notes_by_subtopic(topic_id, subtopic)
        flashcards_content = self._extract_flashcards_by_subtopic(subtopic)
        
        # Track used sections to ensure variety
        used_sections = set()
        
        # First try to generate questions from each section of the notes
        if notes_content:
            for content in notes_content:
                # Skip if we've used this section
                section_id = f"{content.get('title', '')}_{content.get('text', '')[:50]}"
                if section_id in used_sections:
                    continue
                    
                question = self._create_question_from_notes(content, subtopic)
                if question:
                    quiz.append(question)
                    used_sections.add(section_id)
                    
                if len(quiz) >= num_questions:
                    break
        
        # If we still need more questions, try flashcards
        if len(quiz) < num_questions and flashcards_content:
            attempts = 0
            max_attempts = len(flashcards_content) * 2
            while len(quiz) < num_questions and attempts < max_attempts:
                content = random.choice(flashcards_content)
                question = self._create_question_from_flashcards(content, subtopic)
                if question and self._validate_question_for_subtopic(question, subtopic):
                    quiz.append(question)
                attempts += 1
        
        # If we still don't have enough questions, try generating more from unused sections
        if len(quiz) < num_questions and notes_content:
            remaining_content = [c for c in notes_content if f"{c.get('title', '')}_{c.get('text', '')[:50]}" not in used_sections]
            while len(quiz) < num_questions and remaining_content:
                content = random.choice(remaining_content)
                remaining_content.remove(content)  # Don't try this content again
                
                question = self._create_question_from_notes(content, subtopic)
                if question:
                    quiz.append(question)
        
        # Shuffle the quiz questions
        random.shuffle(quiz)
        return quiz[:num_questions]  # Ensure we only return the requested number

    def _validate_question_for_subtopic(self, question, subtopic):
        # Verify that a question is truly related to the given subtopic
        # Check if question text contains subtopic name (strongest indicator)
        if subtopic.lower() in question['question'].lower():
            return True
        
        # Check for subtopic-specific concepts in question and answer
        question_text = question['question'].lower()
        answer_text = question['correct_answer'].lower()
        
        relevant_concepts = self.subtopic_concepts.get(subtopic.lower(), [])
        
        # Count concept occurrences in question and answer
        question_matches = sum(1 for concept in relevant_concepts if concept in question_text)
        answer_matches = sum(1 for concept in relevant_concepts if concept in answer_text)
        
        # Require at least one concept in the question AND one in the answer,
        # or at least two concepts in either question or answer
        return (question_matches >= 1 and answer_matches >= 1) or question_matches >= 2 or answer_matches >= 2

    def _extract_content_from_notes_by_subtopic(self, target_topic_id, target_subtopic):
        # Extract content from notes specific to a subtopic
        content = []
        for (topic_id, subtopic), data in self.notes.items():
            if topic_id == target_topic_id and subtopic.lower() == target_subtopic.lower():
                for page in data.get('pages', []):
                    for section in page.get('sections', []):
                        heading = section.get('heading', '')
                        for item in section.get('content', []):
                            # Include heading in content for context
                            content.append({
                                'title': item.get('title', ''),
                                'heading': heading,
                                'text': item.get('text', ''),
                                'topic': subtopic
                            })
        return content

    def _extract_flashcards_by_subtopic(self, target_subtopic):
        # Extract flashcards specific to a subtopic
        content = []
        for subtopic, cards in self.flashcards.items():
            if subtopic.lower() == target_subtopic.lower():
                for card in cards:
                    content.append({
                        'question': card.get('front', ''),
                        'answer': card.get('back', ''),
                        'topic': subtopic
                    })
        return content

    def generate_alternative_answers(self, correct_answer):
        # Generate simpler, human-like alternative answers for a given correct answer
        alternatives = []
        
        # Shorter version (first sentence)
        if '.' in correct_answer:
            first_sentence = correct_answer.split('.')[0] + '.'
            alternatives.append(first_sentence)
        
        # Version with main concept mentioned
        concepts = self._extract_general_concepts(correct_answer)
        if concepts:
            concept = concepts[0]
            simple = f"{concept.capitalize()} refers to {concept} in economics."
            alternatives.append(simple)
        
        # Very simple version
        if len(correct_answer.split()) > 10:
            words = correct_answer.split()
            simple = ' '.join(words[:10]) + '.'
            alternatives.append(simple)
        
        return alternatives

    def _generate_specific_answer(self, concept, subtopic):
        # Generate a specific, accurate answer for a concept
        # Dictionary of concept definitions for common economic concepts
        concept_definitions = {
            "economic problem": "The economic problem refers to the issue of scarcity: society has limited resources but unlimited wants and needs. This requires making choices about how to allocate these scarce resources. For example, a government must decide how to allocate its limited budget between healthcare, education, defense, and other public services.",
            
            "scarcity": "Scarcity is the fundamental economic problem that arises because resources are limited but human wants are unlimited. This means that individuals, businesses, and societies must make choices about how to allocate these resources efficiently.",
            
            "opportunity cost": "Opportunity cost refers to the value of the next best alternative that is forgone when making a decision. For example, if a student spends time studying for an economics exam instead of going to a concert, the opportunity cost is the enjoyment and experience they would have gained from attending the concert.",
            
            "supply": "Supply refers to the quantity of a good or service that producers are willing and able to offer for sale at various price levels in a given time period. The law of supply states that, all else equal, as the price of a good increases, the quantity supplied will increase.",
            
            "demand": "Demand refers to the quantity of a good or service that consumers are willing and able to purchase at various price levels in a given time period. The law of demand states that, all else equal, as the price of a good increases, the quantity demanded will decrease.",
            
            "market equilibrium": "Market equilibrium occurs at the price and quantity where the quantity demanded equals the quantity supplied. At this point, there is no tendency for prices to change unless there is a shift in either the supply or demand curve.",
            
            "elasticity": "Elasticity measures the responsiveness of one economic variable to changes in another. Price elasticity of demand, for example, measures how responsive quantity demanded is to a change in price.",
            
            "price elasticity": "Price elasticity of demand (PED) measures how responsive quantity demanded is to a change in price. It is calculated as the percentage change in quantity demanded divided by the percentage change in price.",
            
            "economics as a social science": "Economics as a social science studies human behavior in relation to how limited resources are allocated to meet unlimited wants and needs in society. It analyzes individuals, businesses, governments, and entire economies to understand decision-making patterns and their consequences on society.",
            
            "inflation": "Inflation is a sustained increase in the general price level of goods and services in an economy over a period of time. It can be caused by demand-pull factors (too much money chasing too few goods), cost-push factors (rising production costs), or monetary factors (excessive money supply growth).",
            
            "gdp": "Gross Domestic Product (GDP) is the total monetary or market value of all the finished goods and services produced within a country's borders in a specific time period. It serves as a comprehensive measure of a nation's overall economic activity.",
            
            "unemployment": "Unemployment refers to the situation when a person who is actively searching for employment is unable to find work. The unemployment rate is the percentage of the labor force that is unemployed but actively seeking employment and willing to work.",
            
            "competition": "Competition in economics refers to the rivalry among producers or sellers to win consumer business. It can range from perfect competition (many small firms) to monopolistic competition, oligopoly, and monopoly (a single seller).",
            
            # Add subtopic-specific concept definitions
            "supply curve": "A graphical representation showing the relationship between price and quantity supplied, typically upward sloping. It demonstrates how producers respond to different price levels.",
            "factors of production": "The resources used in the production process, including land, labor, capital, and entrepreneurship. These are the essential inputs needed to produce goods and services.",
            "production capacity": "The maximum amount a firm can produce given its current resources and technology. It represents the upper limit of a firm's output capabilities.",
            "demand curve": "A graphical representation showing the relationship between price and quantity demanded, typically downward sloping. It illustrates how consumers respond to different price levels.",
            "consumer surplus": "The difference between what consumers are willing to pay for a good and what they actually pay. It represents the benefit consumers receive from participating in a market.",
            "diminishing marginal utility": "The principle that each additional unit of a good provides less satisfaction than the previous unit. This explains why demand curves typically slope downward.",
            "elastic": "When the percentage change in quantity is greater than the percentage change in price. This indicates high responsiveness to price changes.",
            "inelastic": "When the percentage change in quantity is less than the percentage change in price. This indicates low responsiveness to price changes.",
            "unit elastic": "When the percentage change in quantity equals the percentage change in price. This represents a balanced responsiveness to price changes."
        }
        
        # Check if we have a specific definition for this concept
        concept_lower = concept.lower()
        if concept_lower in concept_definitions:
            return concept_definitions[concept_lower]
            
        # For subtopic-specific concepts, try to generate a reasonable answer
        if subtopic in self.subtopic_concepts:
            if concept_lower in [c.lower() for c in self.subtopic_concepts[subtopic]]:
                # Generate a generic but informative answer based on the subtopic
                subtopic_descriptions = {
                    "supply": "how producers respond to market conditions and price changes",
                    "demand": "how consumers make purchasing decisions based on their preferences and budget constraints",
                    "elasticity": "how economic variables respond to changes in other variables",
                    "market": "how buyers and sellers interact to determine prices and quantities",
                    "competition": "how firms compete with each other in markets",
                    "inflation": "changes in the general price level over time",
                    "unemployment": "the state of being without work despite being willing and able to work",
                    "costs": "the expenses incurred by firms in the production process",
                    "revenue": "the income received by firms from selling goods or services"
                }
        
                description = subtopic_descriptions.get(subtopic.lower(), "how economic principles apply in specific contexts of decision-making")
                return f"{concept.capitalize()} is a key concept in {subtopic} economics. It refers to {description}."
            
        # Fallback for unknown concepts
        return f"{concept.capitalize()} is a concept in economics that relates to how economic agents make decisions about resource allocation within the context of {subtopic}."

def generate_quiz(topic_id=None, subtopic=None, num_questions=5):
    # Helper function to generate a quiz for a specific subtopic
    generator = QuizGenerator()
    if topic_id is not None and subtopic is not None:
        return generator.generate_quiz_for_subtopic(topic_id, subtopic, num_questions)
    else:
        # Fallback to generic quiz if no topic specified
        return []

if __name__ == "__main__":
    # Example usage
    quiz = generate_quiz(topic_id=41, subtopic="Demand", num_questions=5)
    
    for i, question in enumerate(quiz, 1):
        print(f"\nQuestion {i}:")
        print(f"Topic: {question['topic']}")
        print(f"Question: {question['question']}")
        print(f"Correct Answer: {question['correct_answer']}") 
        
        # Generate and print alternative acceptable answers
        alternatives = QuizGenerator().generate_alternative_answers(question['correct_answer'])
        if alternatives:
            print("Alternative Answers:")
            for alt in alternatives:
                print(f"- {alt}") 