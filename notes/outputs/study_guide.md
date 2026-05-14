# Statistics and Probability — Cheat Sheet

## TL;DR
- **PDF and CDF**: Learn the probability density function (PDF) for continuous variables and how to find the cumulative distribution function (CDF).
- **Expected Value**: Calculate expectation using $\int x \cdot f(x) \, dx$.
- **Variable Transformations**: Understand how to transform random variables and find new distributions.
- **Joint Distributions**: Analyze joint PDFs and calculate marginal distributions.
- **Common Calculations**: Expectation, variance, conditional probability, and probability transformations.

## Key Terms

| Term                                | Definition                                                                 |
|-------------------------------------|----------------------------------------------------------------------------|
| <span class="key">PDF</span>        | Probability density function; describes the likelihood for a continuous random variable to take on a specific value. |
| <span class="key">CDF</span>        | Cumulative distribution function; the probability that a random variable is less than or equal to a certain value. |
| <span class="key">Expected Value</span>| Average value of a random variable, symbolized by $E(X)$. |
| <span class="key">Variance</span>   | Measure of the dispersion of a set of values; computed as $Var(X) = E(X^2) - (E(X))^2$. |
| <span class="key">Transformation</span> | The process of changing a random variable into another using a function. |
| <span class="key">Joint PDF</span>  | Probability distribution for two random variables, $f(x,y)$. |
| <span class="key">Marginal PDF</span>| Distribution of one variable irrespective of the other variable in a joint distribution. |

## Core Concepts

### Probability Density Function (PDF)
- **Definition**: Describes the likelihood of a random variable to take a particular value. Integral over its support equals 1.
- **Example**: $f_X(x) = \frac{6x + 7}{200}, 3 \leq x \leq 8$.

### Cumulative Distribution Function (CDF)
- **Definition**: CDF gives the probability that a random variable is less than or equal to a certain value.
- **Relationship**: $F_X(x) = P(X \leq x) = \int_{-\infty}^{x} f_X(t) \, dt$.
- **Example**: For $Y = g(X)$, $F_Y(y) = F_X(g^{-1}(y))$.

### Expected Value
- **Definition**: The mean or average of all possible values, weighted by their probabilities.
- **Formula**: $E(X) = \int x \cdot f_X(x) \, dx$.

### Transformations of Random Variables
- **Process**: If $Y = g(X)$, find $f_Y(y) = f_X(g^{-1}(y)) \cdot \left| \frac{d}{dy} [g^{-1}(y)] \right|$.
- **Example**: $g(x) = \sqrt{x+1}, g^{-1}(y) = y^2 - 1$.

### Joint Probability Density
- **Definition**: The probability law for two continuous random variables.
- **Formula**: $f(x,y) = \frac{3x + 2y}{C}$ with given constraints.
- **Marginal Distributions**: Integrate over one variable, $f_X(x) = \int f(x,y) \, dy$.

## Formulas / Rules

| Formula                              | Symbols                        | Application                                     |
|--------------------------------------|--------------------------------|-------------------------------------------------|
| $1 = \int f_X(x) \, dx$              | $f_X(x)$: PDF                  | Ensures PDF is valid                             |
| $E(X) = \int x \cdot f_X(x) \, dx$   | $E(X)$: expected value         | Calculate mean of continuous variable            |
| $Var(X)=E(X^2) - (E(X))^2$           | Variance $Var(X)$              | Measure of spread                               |
| $F_X(x) = \int_{-\infty}^{x} f_X(t) \, dt$ | $F_X(x)$: CDF                | Cumulative probability                         |

## Worked Mini-Examples

- **Find $C$ for PDF**: $1 = \int_3^8 \frac{6x+7}{C} \, dx \rightarrow C = 200$.
- **Transform $Y = \sqrt{x+1}$**: $f_Y(y) = f_X(g^{-1}(y)) \cdot \left|\frac{d}{dy}(y^2-1)\right|$.
- **Expected Value Example**: $E(X) = \int_3^8 x \frac{6x+7}{200} \, dx = 16$.

## Common Mistakes / Gotchas

- **Ignoring Validity of PDFs**: Ensure the integral of the PDF over its support equals 1.
- **Misapplying Transformations**: Always consider the domain for transformed variables.
- **Confusing Marginalization**: Remember to integrate out other variables for marginal PDFs.

## Quick-Check Questions

1. What does the integral of a PDF over its entire support equal?
2. How do you find the CDF from a PDF?
3. What is the expected value of a random variable indicative of?
4. How is the variance of a random variable calculated?
5. What is the first step in transforming a random variable?

## Answers

1. **1**; the integral of a PDF over its entire support must equal 1.
2. **CDF**: $F_X(x) = \int_{-\infty}^{x} f_X(t) \, dt$.
3. **Mean** of the possible values, weighted by probabilities.
4. **Variance**: $Var(X) = E(X^2) - (E(X))^2$.
5. **Determine** the form of $Y = g(X)$ and compute $g^{-1}(y)$.