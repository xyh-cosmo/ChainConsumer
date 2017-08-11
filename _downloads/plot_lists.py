"""
==================
Using List Options
==================

Utilise all the list options in the configuration!

This is a general example to illustrate that most parameters
that you can pass to the configuration methods accept lists.

"""

import numpy as np
from numpy.random import normal, multivariate_normal
from chainconsumer import ChainConsumer

if __name__ == "__main__":
    np.random.seed(2)
    cov = normal(size=(2, 2)) + np.identity(2)
    d1 = multivariate_normal(normal(size=2), 0.5 * (cov + cov.T), size=100000)
    cov = normal(size=(2, 2)) + np.identity(2)
    d2 = multivariate_normal(normal(size=2), 0.5 * (cov + cov.T), size=100000)
    cov = normal(size=(2, 2)) + np.identity(2)
    d3 = multivariate_normal(normal(size=2), 0.5 * (cov + cov.T), size=1000000)

    c = ChainConsumer()
    c.add_chain(d1, parameters=["$x$", "$y$"])
    c.add_chain(d2)
    c.add_chain(d3)

    c.configure(linestyles=["-", "--", "-"], linewidths=[1.0, 3.0, 1.0],
                bins=[3.0, 1.0, 1.0], colors=["#1E88E5", "#D32F2F", "#111111"],
                smooth=[0, 1, 2], shade=[True, True, False],
                shade_alpha=[0.2, 0.1, 0.0], bar_shade=[True, False, False])
    fig = c.plotter.plot()

    fig.set_size_inches(4.5 + fig.get_size_inches())  # Resize fig for doco. You don't need this.
