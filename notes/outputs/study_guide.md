# LLM Fundamentals — Cheat Sheet

## TL;DR
- **LLMs (Large Language Models)** leverage immense amounts of data and parameters to process language.
- **Transformer Architecture** is central to LLMs, using *self-attention* for parallel processing.
- **Pre-training & Fine-tuning** are crucial steps: generic knowledge base first, task-specific second.
- **BERT vs. GPT**: BERT is bi-directional; GPT is uni-directional.
- **Tokenization**: Divides text into understandable units for the model.

## Key Terms

| Term                          | Definition                                                                 |
|-------------------------------|-----------------------------------------------------------------------------|
| <span class="key">LLM</span>  | Models handling vast language data, using billions of parameters.        |
| Transformer                   | Model architecture utilizing *attention* mechanisms for language tasks.  |
| Self-Attention                | Mechanism allowing models to focus on different parts of the input sequence. |
| Pre-training                  | Initial training phase on a general corpus.                              |
| Fine-tuning                   | Adjusting a pre-trained model for specific tasks.                       |

## Core Concepts

### Transformer Architecture
- **Model Components**: Encoder-Decoder; focus on **Self-Attention**.
- **Self-Attention**: Maps the input sequence onto itself; allows model to weigh importance.
- **Parallel Processing**: Enables faster computations over sequential models.

### Tokenization
- **Purpose**: Breaks text into smaller units (tokens).
- **Methods**:
  - <span class="tip">WordPiece</span>: Subword tokenization (used in BERT).
  - <span class="tip">Byte-Pair Encoding (BPE)</span>: Adaptively splits words more common to rare; beneficial for GPT.

### Pre-training and Fine-tuning
- **Pre-training**:
  - Trains model on generic tasks (e.g., cloze tasks for BERT).
- **Fine-tuning**:
  - Tailored adjustment towards specific downstream tasks like classification or Q&A.

### BERT vs. GPT
- **BERT (Bidirectional Encoder Representations from Transformers)**:
  - **Training**: Bi-directional. Masks tokens to predict missing input values.
  - **Use**: Generally for tasks requiring understanding of context.
- **GPT (Generative Pre-trained Transformer)**:
  - **Training**: Uni-directional. Predicts next word in sequence.
  - **Use**: Typically for generative tasks such as text completion.

## Formulas / Rules

| Formula                               | Symbols       | When to Apply                          |
|---------------------------------------|---------------|----------------------------------------|
| Self-Attention Score: $QK^T / \sqrt{d_k}$ | $Q, K, d_k$   | Calculating attention weights.         |
| Activation of Attention: $Softmax(z)$ | $z$           | Normalizing attention scores for input. |

## Worked Mini-Examples

- **Example**: Given text "The cat sat on the mat", predict masked word.
  - **Key Step**: Input "The [MASK] sat on the mat".
  - **Answer**: BERT predicts "cat".

- **Example**: Complete sentence using GPT: "Once upon a time, a girl ventured".
  - **Key Step**: Predict subsequent words based on prior context.
  - **Answer**: GPT results in continuation — "into a dense forest."

## Common Mistakes / Gotchas
- Misunderstanding **tokenization methods** can affect model input structure.
- **Mixing pre-training tasks**: Bi-directional (BERT) vs. Uni-directional (GPT) contexts.
- Overlooking **fine-tuning necessity**: Model may not perform specific tasks without it.

## Quick-Check Questions
1. What is the main advantage of using the Transformer architecture?
2. How does self-attention differ from traditional RNN attention?
3. Define the difference between pre-training and fine-tuning.
4. Explain the key distinction between BERT and GPT language models.
5. What is the role of tokenization in LLMs?

## Answers
1. Enables parallel processing, leading to faster computations.
2. Self-attention allows each word to attend to every other word in the input.
3. Pre-training involves learning on generic tasks; fine-tuning tailors the model for specific tasks.
4. BERT is bi-directional for context understanding, while GPT is uni-directional for text generation.
5. Tokenization breaks text into comprehensible units for the model.