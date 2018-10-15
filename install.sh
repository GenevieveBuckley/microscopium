#!/usr/bin/env bash

# microscopium conda environment setup

conda env create --file environment.yml
source activate mic

# Development installation of bokeh
# https://bokeh.pydata.org/en/latest/docs/dev_guide/setup.html#devguide-setup

cd ..
git clone https://github.com/bokeh/bokeh.git
cd bokeh
conda install `python scripts/deps.py build run test` -c bokeh
cd bokehjs
npm install -g npm
npm install --no-save
cd ..
python setup.py develop --build-js
python -m bokeh info
