.. |br| raw:: html

   <br />

pySYD: |br| Automated Measurements |br| of Global Asteroseismic Parameters
==========================================================================

``pySYD`` is an open-source python package to detect solar-like oscillations and measure global asteroseismic parameters. ``pySYD`` provides best-fit values and uncertainties for the following parameters:

- Granulation background, including characteristic time scales and amplitudes
- Frequency of maximum power
- Large frequency separation
- Mean oscillation amplitudes

For a basic introduction to these parameters and asteroseismic data analysis of solar-like oscillators see  `Bedding et al. 2014 <https://ui.adsabs.harvard.edu/abs/2014aste.book...60B/abstract>`_.

``pySYD`` is a python-based implementation of the IDL-based SYD pipeline `(Huber et al. 2009) <https://ui.adsabs.harvard.edu/abs/2009CoAst.160...74H/abstract>`_, which was extensively used to measure asteroseismic parameters for Kepler stars. Papers based on asteroseismic parameters measured using the ``SYD`` pipeline include `Huber et al. 2011 <https://ui.adsabs.harvard.edu/abs/2011ApJ...743..143H/abstract>`_, `Chaplin et al. 2014 <https://ui.adsabs.harvard.edu/abs/2014ApJS..210....1C/abstract>`_, `Serenelli et al. 2017 <https://ui.adsabs.harvard.edu/abs/2017ApJS..233...23S/abstract>`_ and `Yu et al. 2018 <https://ui.adsabs.harvard.edu/abs/2018ApJS..236...42Y/abstract>`_.

``pySYD`` adapts the well-tested methodology from ``SYD`` while also improving these existing analyses and expanding upon numerous new
(optional) features. Improvements include:

- Automated best-fit background model selection
- Parallel processing
- Easily accessible + command-line friendly interface
- Ability to save samples for further analyses

Please cite our recent JOSS paper `Chontos+2021 <https://arxiv.org/abs/2108.00582>`_ if you make use of ``pySYD`` in your work.

Code contributions are welcome and should be submitted as a pull request.

Bug reports and feature requests should be posted to the `GitHub issue tracker <https://github.com/ashleychontos/pySYD/issues>`_.

**Contents:**

.. toctree::
   :maxdepth: 1

   quickstart
   overview
   examples
   cli
   performance
   advanced
   api
   
Indices and tables for the source code
======================================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
