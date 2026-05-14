# Statistics and Probability 2 — Cheat Sheet

## TL;DR
- **Probability Density Function (PDF):** Describes continuous random variables' distributions.
- **Cumulative Distribution Function (CDF):** $F_X(x) = P(X \leq x)$; integrates the PDF from $-\infty$ to $x$.
- **Expected Value (EV):** Average outcome expected from a random variable; calculated via $\int xf(x) \, dx$.
- **Transformations:** Finding PDFs and CDFs for new variables $Y = g(X)$ using change of variables.
- **Joint Distributions:** Describe multiple random variables; marginalize for singular distributions.

## Key Terms

| Term | Definition |
|---|---|
| <span class="key">PDF</span> | Describes the probability of a continuous random variable at a specific point. |
| <span class="key">CDF</span> | Probability that a random variable takes on a value less than or equal to a specific value. |
| <span class="key">Expected Value</span> | Average of all possible values weighted by their probabilities. |
| <span class="key">Transformation</span> | A method to find the distribution of a function of a random variable. |
| <span class="key">Joint Distribution</span> | Probability distribution for multiple random variables simultaneously. |

## Core Concepts

### Probability Density Function (PDF)
- **Concept:** Function $f_X(x)$ where $P(a \leq X \leq b) = \int_a^b f_X(x) \, dx$.
- **Normalization:** $\int_{-\infty}^\infty f_X(x) \, dx = 1$.
- **Example:** $f_X(x) = \frac{6x+7}{C}, \, 3 \leq x \leq 8$; Find $C$ such that $\int_3^8 f_X(x) \, dx = 1$.

### Cumulative Distribution Function (CDF)
- **Concept:** $F_X(x) = \int_{-\infty}^x f_X(t) \, dt$.
- **Property:** $F_X$ is non-decreasing and right-continuous.
- **Example:** Use CDF to find $P(Y \leq y)$ for transformation $Y = \sqrt{X+1}$ using $F_X$.

### Expected Value & Variance
- **Expected Value:** $E(X) = \int_3^8 x \frac{6x+7}{200} \, dx = 16$.
- **Variance:** $Var(X) = E(X^2) - (E(X))^2$.
- **Example:** $E(X^2)= \int_{-1}^{2} x^2 \frac{x^2+1}{9} \, dx = \frac{11}{5}$; $Var(X) = \frac{61}{90}$.

### Probability Distribution of Transformed Variables
- **Concept:** $Y = g(X)$ maps $X$ to $Y$. Find $f_Y(y)$ using change of variables.
- **Steps:** 
  - Find inverse: $g^{-1}(y)$.
  - Calculate $\frac{d}{dy}[g^{-1}(y)]$.
  - Transform PDF: $f_Y(y) = f_X(g^{-1}(y)) \left| \frac{d}{dy}[g^{-1}(y)] \right|$.

### Joint Probability Distribution
- **Concept:** $f(x, y)$ for two variables $X, Y$.
- **Marginal Distributions:**
  - $f_X(x) = \int f(x, y) \, dy$
  - $f_Y(y) = \int f(x, y) \, dx$
- **Example:** $f(x,y) = \frac{3x + 2y}{C}$; find $C$ & boundaries.

## Formulas / Rules

| Formula | Symbols | Application |
|---|---|---|
| $f_X(x) = \text{given function}$ | $f_X(x), x \in [a, b]$ | Determine $C$ for PDFs. |
| $F_X(x) = P(X \leq x)$ | $F_X(x)$ | Accumulated probability at $x$. |
| $E(X)$ | $E(X) = \int x f_X(x) \, dx$ | Calculate expected outcome. |
| $Var(X)$ | $E(X^2) - (E(X))^2$ | Measure spread of $X$. |
| $f_Y(y)$ | $f_Y(y) = f_X(g^{-1}(y)) \left| \frac{d}{dy} [g^{-1}(y)] \right|$ | Derive $f_Y(y)$ from $g(X)$. |

## Worked Mini-Examples

1. **Normalization of PDF:**
   - Given $f_X(x) = \frac{6x+7}{C}$, solve $\int_3^8 f_X(x) \, dx = 1 \Rightarrow C = 200$.
   
2. **Finding CDF:**
   - $F_X(x) = \int_3^x \frac{6t+7}{200} \, dt$.

3. **Transformation with $Y = g(X)$:**
   - $f_Y(y) = f_X(y^2-1) \cdot 2y$ if $Y = \sqrt{X+1}$.

4. **Joint PDF:**
   - $f(x,y) = \frac{3x+2y}{240}$ with constraints such as $x + 2y \leq 10$.

## Common Mistakes / Gotchas

- **Ignore Normalization:** Always check if the integral of PDF equals 1.
- **Miss Limits in Integration:** Carefully define integration bounds for CDFs and EVs.
- **Overlook Transformations:** Apply correct derivatives when changing variables.
- **Confuse Marginals:** Marginal distributions require integration over unused variables' domain.

## Quick-Check Questions

1. What ensures a function is a valid PDF?
2. How do you compute $E(X)$ given $f_X(x)$?
3. What is the relationship between CDF and PDF?
4. How do you find $f_Y(y)$ for $Y = g(X)$?
5. Describe a joint probability distribution's support.

## Answers

1. The integral of the PDF over its entire range must equal 1.
2. By $\int x f_X(x) \, dx$ over the support of $X$.
3. PDF is the derivative of CDF with respect to $x$.
4. Use the method: $f_Y(y) = f_X(g^{-1}(y)) \left| \frac{d}{dy}[g^{-1}(y)] \right|$.
5. The set where the joint PDF $f(x, y) > 0$.