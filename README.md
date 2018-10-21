Microscopium
============

Unsupervised clustering and dataset exploration for high content screens.

[![Build Status](https://travis-ci.org/microscopium/microscopium.svg?branch=master)](https://travis-ci.org/microscopium/microscopium)
[![Coverage Status](https://img.shields.io/coveralls/microscopium/microscopium.svg)](https://coveralls.io/r/microscopium/microscopium?branch=master)
[![Gitter](https://img.shields.io/gitter/room/nwjs/nw.js.svg)](https://gitter.im/microscopium/microscopium?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

## See microscopium in action

Public dataset BBBC021 from the [Broad Bioimage Benchmark Collection](https://data.broadinstitute.org/bbbc/BBBC021/) with t-SNE image embedding:

![microscopium_bbbc021](https://user-images.githubusercontent.com/30920819/47265048-999aa300-d56d-11e8-8089-9b075c074b9d.gif)

Demonstration of 3D image features:

![microscopium_3d-features](https://user-images.githubusercontent.com/30920819/47265066-c5b62400-d56d-11e8-92a9-b51ca2975435.gif)


## For developers
We encourage pull requests - please get in touch if you think you might like to contribute.


### License

This project uses the 3-clause BSD license. See `LICENSE.txt`.

### Development installation
```
git clone https://github.com/microscopium/microscopium.git
pip install -r requirements.txt
cd microscopium
pip install -e .
```

### Serving the web app

To run the web app locally in your browser:

`python microscopium/serve.py tests/testdata/images/data.csv`

You should then be able to see the app in your web browser at:
http://localhost:5000

`python microscopium/serve.oy tests/testdata/images/data.csv -P 5001`

This specifies the port number as 5001, and the app will run locally at: http://localhost:5001/

For more information, run `python microscopium/serve.py --help`

