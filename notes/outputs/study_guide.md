# Expected Value, CDF, Change of Variable — Cheat Sheet

## TL;DR
- **Expected Value ($E(X)$):** Average outcome; integral of $x$ times PDF.
- **CDF ($F_X(x)$):** Probability $X \leq x$; integral of PDF from $-\infty$ to $x$.
- **Change of Variables:** Transform PDFs/CDFs under variable transformation.
- **Transforming PDFs:** Use inverse function and Jacobian for new PDF.
- **Common Formulas:** $E(X) = \int x f_X(x) \, dx$, $F_X(x) = \int_{-\infty}^{x} f_X(t) \, dt$.

## Key Terms
| Term | Definition |
|------|------------|
| <span class="key">PDF</span> | Probability Density Function; derivative of CDF. |
| <span class="key">CDF</span> | Cumulative Distribution Function; probability $X \leq x$. |
| <span class="key">Expected Value</span> | Mean of a random variable's probability distribution. |
| <span class="key">Change of Variable</span> | Technique to transform random variables. |
| <span class="key">Transformation</span> | Function changing random variable $X$ to $Y=g(X)$. |

## Core Concepts

### Expected Value
- **Concept:** Expected scalar outcome of a random variable.
- **Formula:** $E(X) = \int_{\text{range}} x f_X(x) \, dx$.
- **Example:** If $f_X(x) = (6x+7)/200$, $E(X) = \int_3^8 x f_X(x) \, dx = 16$.

### Cumulative Distribution Function (CDF)
- **Concept:** Probability a random variable $X$ is $\leq x$.
- **Formula:** $F_X(x) = \int_{-\infty}^x f_X(t) \, dt$.
- **Example:** $F_X(x) = (x^2 + 1)/9$ for $-1 < x < 2$.

### Change of Variable
- **Concept:** When $Y = g(X)$, derive PDF of $Y$ from $X$.
- **PDF Formula:** $f_Y(y) = f_X(g^{-1}(y)) \left| \frac{d}{dy} g^{-1}(y) \right|$.
- **Example:** For $Y = \sqrt{X+1}$ with $g^{-1}(y) = y^2 - 1$, compute $f_Y(y)$.

## Formulas / Rules

| Formula | Symbols | Application |
|---------|---------|-------------|
| $E(X) = \int x f_X(x) \, dx$ | $x$, $f_X(x)$ | Calculate expected value. |
| $F_X(x) = \int_{-\infty}^x f_X(t) \, dt$ | $x$, $f_X(x)$ | Calculate CDF. |
| $f_Y(y) = f_X(g^{-1}(y)) \left| \frac{d}{dy} g^{-1}(y) \right|$ | $g^{-1}(y)$, $\frac{d}{dy}$ | Change of variable for PDFs. |

## Worked Mini-Examples

1. **Finding C:**  
   $1 = \int_3^8 \frac{6x+7}{C} \, dx \Rightarrow C = 200$

2. **CDF from PDF:**  
   $F_X(x) = \frac{x^2 + 1}{9}$ on $-1 < x < 2$

3. **PDF Transformation:**  
   For $g(x) = \sqrt{x+1}$, $g^{-1}(y) = y^2 - 1$,  
   $f_Y(y) = f_X(y^2 - 1) \cdot \left| \frac{d}{dy}(y^2 - 1) \right|$

## Common Mistakes / Gotchas
- **Forgetting normalization** of PDFs; always check $\int f_X(x) \, dx = 1$.
- **Incorrect Jacobian** sign; use absolute value when transforming variables.
- **Support mismatch:** Adjust limits properly for transformed variables.

## Quick-Check Questions
1. What does $E(X)$ represent?
2. How do you compute a CDF from a PDF?
3. What is the role of the Jacobian in change of variables?
4. What condition must a PDF satisfy?
5. How does $F_X(x)$ relate to probabilities?

## Answers
1. The mean or expected outcome of a random variable.
2. Integrate the PDF from $-\infty$ to $x$.
3. It adjusts for scaling during variable transformation.
4. It must integrate to 1 over its range.
5. $F_X(x) = P(X \leq x)$.