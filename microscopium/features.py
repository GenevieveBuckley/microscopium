import itertools as it
import numpy as np
from scipy.stats.mstats import mquantiles
from scipy import ndimage as nd
from scipy import sparse
from skimage import morphology as skmorph
from skimage import filters as imfilter, measure, util
from sklearn.neighbors import NearestNeighbors
from six.moves import range
import cytoolz as tz
from ._util import normalise_random_state


def normalize_vectors(v):
    """Interpret a matrix as a row of vectors, and divide each by its norm.

    0-vectors are left changed.

    Parameters
    ----------
    v : array of float, shape (M, N)
        M points of dimension N.

    Returns
    -------
    v1 : array of float, shape (M, N)
        The vectors divided by their norm.

    Examples
    --------
    >>> vs = np.array([[2., 0.], [0., 4.], [0., 0.]])
    >>> normalize_vectors(vs)
    array([[1., 0.],
           [0., 1.],
           [0., 0.]])
    """
    v_norm = np.sqrt((v ** 2).sum(axis=1))
    v_norm[v_norm == 0] = 1.  # ignore 0-vectors for division
    v1 = v / v_norm[..., np.newaxis]
    return v1


def triplet_angles(points, indices):
    """Compute the angles formed by point triplets.

    Parameters
    ----------
    points : array of float, shape (M, N)
        Set of M points in N-dimensional space.
    indices : array of int, shape (Q, 3)
        Set of Q index triplets, in order (root, leaf1, leaf2). Thus,
        the angle is computed between the vectors
            (points[leaf1] - points[root])
        and
            (points[leaf2] - points[root]).

    Returns
    -------
    angles : array of float, shape (Q,)
        The desired angles.
    """
    angles = np.zeros(len(indices), np.double)
    roots = points[indices[:, 0]]
    leaf1 = points[indices[:, 1]]
    leaf2 = points[indices[:, 2]]
    u = normalize_vectors(leaf1 - roots)
    v = normalize_vectors(leaf2 - roots)
    cosines = (u * v).sum(axis=1)
    cosines[cosines > 1] = 1
    cosines[cosines < -1] = -1
    angles = np.arccos(cosines)
    return angles


def nearest_neighbors(lab_im, n=3, quantiles=[0.05, 0.25, 0.5, 0.75, 0.95]):
    """Find the distances to and angle between the n nearest neighbors.

    Parameters
    ----------
    lab_im : 2D array of int
        An image of labeled objects.
    n : int, optional
        How many nearest neighbors to check. (Angle is always between
        the two nearest only.)
    quantiles : list of float in [0, 1], optional
        Which quantiles of the features to compute.

    Returns
    -------
    nei : 1D array of float, shape (5 * (n + 1),)
        The quantiles of sines, cosines, angles, and `n` nearest neighbor
        distances.
    names : list of string
        The name of each feature.
    """
    if lab_im.dtype == bool:
        lab_im = nd.label(lab_im)[0]
    centroids = np.array([p.centroid for p in measure.regionprops(lab_im)])
    nbrs = (NearestNeighbors(n_neighbors=(n + 1), algorithm='kd_tree').
                         fit(centroids))
    distances, indices = nbrs.kneighbors(centroids)
    angles = triplet_angles(centroids, indices[:, :3])
    # ignore order/orientation of vectors, only measure acute angles
    angles[angles > np.pi] = 2 * np.pi - angles[angles > np.pi]
    distances[:, 0] = angles
    sines, cosines = np.sin(angles), np.cos(angles)
    features = np.hstack((sines[:, np.newaxis], cosines[:, np.newaxis],
                          distances))
    nei = mquantiles(features, quantiles, axis=0).ravel()
    colnames = (['sin-theta', 'cos-theta', 'theta'] +
                ['d-neighbor-%i-' % i for i in range(1, n + 1)])
    names = ['%s-percentile-%i' % (colname, int(q * 100))
             for colname, q in it.product(colnames, quantiles)]
    return nei, names


# threshold and labeling number of objects, statistics about object size and
# shape
def intensity_object_features(im, threshold=None, adaptive_t_radius=51,
                              sample_size=None, random_seed=None):
    """Segment objects based on intensity threshold and compute properties.

    Parameters
    ----------
    im : 2D np.ndarray of float or uint8.
        The input image.
    threshold : float, optional
        A threshold for the image to determine objects: connected pixels
        above this threshold will be considered objects. If ``None``
        (default), the threshold will be automatically determined with
        both Otsu's method and a locally adaptive threshold.
    adaptive_t_radius : int, optional
        The radius to calculate background with adaptive threshold.
    sample_size : int, optional
        Sample this many objects randomly, rather than measuring all
        objects.
    random_seed: int, or numpy RandomState instance, optional
        An optional random number generator or seed from which to draw
        samples.

    Returns
    -------
    f : 1D np.ndarray of float
        The feature vector.
    names : list of string
        The list of feature names.
    """
    if threshold is None:
        tim1 = im > imfilter.threshold_otsu(im)
        f1, names1 = object_features(tim1, im, sample_size=sample_size,
                                     random_seed=random_seed)
        names1 = ['otsu-threshold-' + name for name in names1]
        f = f1
        names = names1
        if im.ndim == 2:
            tim2 = im > imfilter.threshold_local(im, adaptive_t_radius)
            f2, names2 = object_features(tim2, im, sample_size=sample_size,
                                         random_seed=random_seed)
            names2 = ['adaptive-threshold-' + name for name in names2]
            f = np.concatenate([f1, f2])
            names = names1 + names2
    else:
        tim = im > threshold
        f, names = object_features(tim, im, sample_size=sample_size,
                                   random_seed=random_seed)
    return f, names


def object_features(bin_im, im, erode=2, sample_size=None, random_seed=None):
    """Compute features about objects in a binary image.

    Parameters
    ----------
    bin_im : 2D np.ndarray of bool
        The image of objects.
    im : 2D np.ndarray of float or uint8
        The actual image.
    erode : int, optional
        Radius of erosion of objects.
    sample_size : int, optional
        Sample this many objects randomly, rather than measuring all
        objects.
    random_seed: int, or numpy RandomState instance, optional
        An optional random number generator or seed from which to draw
        samples.

    Returns
    -------
    fs : 1D np.ndarray of float
        The feature vector.
    names : list of string
        The names of each feature.
    """
    random = normalise_random_state(random_seed)
    if im.ndim == 2:
        selem = skmorph.disk(erode)
    elif im.ndim == 3:
        selem = skmorph.ball(erode)
    else:
        raise ValueError(f'Unexpected number of image dimensions: {im.ndim}')
    if erode > 0:
        bin_im = nd.binary_opening(bin_im, selem)
    lab_im, n_objs = nd.label(bin_im)
    if sample_size is None:
        sample_size = n_objs
        sample_indices = np.arange(n_objs)
    else:
        sample_indices = random.randint(0, n_objs, size=sample_size)
    if im.ndim == 2:
        prop_names = ['area', 'eccentricity', 'euler_number', 'extent',
                      'min_intensity', 'mean_intensity', 'max_intensity',
                      'solidity']
    elif im.ndim == 3:
        prop_names = ['area', 'euler_number', 'extent',
                      'min_intensity', 'mean_intensity', 'max_intensity',
                      'solidity']  # FYI: solidity may be very slow for 3D
    objects = measure.regionprops(lab_im, intensity_image=im)
    properties = np.empty((sample_size, len(prop_names)), dtype=np.float)
    for i, j in enumerate(sample_indices):
        properties[i] = [getattr(objects[j], prop) for prop in prop_names]
    quantiles = [0.05, 0.25, 0.5, 0.75, 0.95]
    feature_quantiles = mquantiles(properties, quantiles, axis=0).T
    fs = np.concatenate([np.array([n_objs], np.float),
                         feature_quantiles.ravel()])
    names = (['num-objs'] +
             ['%s-percentile%i' % (prop, int(q * 100))
              for prop, q in it.product(prop_names, quantiles)])
    return fs, names


def fraction_positive(bin_im, positive_im, erode=2, overlap_thresh=0.9,
                      bin_name='nuclei', positive_name='tf'):
    """Compute fraction of objects in bin_im overlapping positive_im.

    The purpose of this function is to compute the fraction of nuclei
    that express a particular transcription factor. By providing the
    thresholded DAPI channel as `bin_im` and the thresholded TF channel
    as `positive_im`, this fraction can be computed.

    Parameters
    ----------
    bin_im : 2D array of bool
        The image of objects being tested.
    positive_im : 2D array of bool
        The image of positive objects.
    erode : int, optional
        Radius of structuring element used to smooth input images.
    overlap_thresh : float, optional
        The minimum amount of overlap between an object in `bin_im` and
        the `positive_im` to consider that object "positive".
    bin_name : string, optional
        The name of the objects being tested.
    positive_name : string, optional
        The name of the property being measured.

    Returns
    -------
    f : 1D array of float, shape (1,)
        The feature vector.
    name : list of string, length 1
        The name of the feature.

    Examples
    --------
    >>> bin_im = np.array([[1, 1, 0],
    ...                    [0, 0, 0],
    ...                    [1, 1, 1]], dtype=bool)
    >>> pos_im = np.array([[1, 0, 0],
    ...                    [0, 1, 1],
    ...                    [0, 1, 1]], dtype=bool)
    >>> f = fraction_positive(bin_im, pos_im, erode=0, overlap_thresh=0.6)
    >>> f[0]
    array([0.5])
    >>> f[1][0]
    'frac-nuclei-pos-tf-erode-0-thresh-0.60'
    """
    selem = skmorph.disk(erode)
    if erode > 0:
        bin_im = nd.binary_opening(bin_im, selem)
        positive_im = nd.binary_opening(positive_im, selem)
    lab_im = nd.label(bin_im)[0].ravel()
    pos_im = positive_im.ravel().astype(int)
    counts = sparse.coo_matrix((np.ones(lab_im.size),
                                (lab_im, pos_im))).todense()
    means = counts[:, 1] / np.sum(counts, axis=1)
    f = np.array([np.mean(means[1:] > overlap_thresh)])
    name = ['frac-%s-pos-%s-erode-%i-thresh-%.2f' %
            (bin_name, positive_name, erode, overlap_thresh)]
    return f, name


def nuclei_per_cell_histogram(nuc_im, cell_im, max_value=10):
    """Compute the histogram of nucleus count per cell object.

    Counts above or below max_value and min_value are clipped.

    Parameters
    ----------
    nuc_im : array of bool or int
        An image of nucleus objects, binary or labelled.
    cell_im : array of bool or int
        An image of cell objects, binary or labelled.
    max_value : int, optional
        The highest nucleus count we expect. Anything above this will
        be clipped to ``max_value + 1``.

    Returns
    -------
    fs : array of float, shape ``(max_value - min_value + 2,)``.
        The proportion of cells with each nucleus counts.
    names : list of string, same length as fs
        The name of each feature.
    """
    names = [('cells-with-%i-nuclei' % n) for n in range(max_value + 1)]
    names.append('cells-with->%i-nuclei' % max_value)
    nuc_lab = nd.label(nuc_im)[0]
    cell_lab = nd.label(cell_im)[0]
    match = np.vstack((nuc_lab.ravel(), cell_lab.ravel())).T
    match = match[(match.sum(axis=1) != 0), :]
    match = util.unique_rows(match).astype(np.int64)
    # number of nuclei in each cell
    cells = np.bincount(match[:, 1])
    # number of cells with x nuclei
    nhist = np.bincount(cells, minlength=max_value + 2)
    total = np.sum(nhist)
    fs = np.zeros((max_value + 2), np.float)
    fs[:(max_value + 1)] = nhist[:(max_value + 1)]
    fs[max_value + 1] = np.sum(nhist[(max_value + 1):])
    fs /= total
    return fs, names


@tz.curry
def default_feature_map(image, threshold=None,
                        channels=None, channel_names=None,
                        sample_size=None, random_seed=None):
    """Compute a feature vector from a multi-channel image.

    Parameters
    ----------
    image : array, shape (M, N, 3)
        The input image.
    threshold : tuple of float, shape (3,), optional
        The intensity threshold for object detection on each channel.
    channels : list of int, optional
        Which channels to use for feature computation
    channel_names : list of string, optional
        The channel names corresponding to ``channels``.
    sample_size : int, optional
        For features based on quantiles, sample this many objects
        rather than computing full distribution. This can considerably
        speed up computation with little cost to feature accuracy.
    random_seed: int, or numpy RandomState instance, optional
        An optional random number generator or seed from which to draw
        samples.

    Returns
    -------
    fs : 1D array of float
        The features of the image.
    names : list of string
        The feature names.
    """
    all_fs, all_names = [], []
    # process all image channels unless otherwise specified:
    if channels is None:
        channels = range(image.shape[-1])
    images = [np.array(image[..., i]) for i in channels]
    if channel_names is None:
        channel_names = ['chan{}'.format(i) for i in channels]
    for im, prefix in zip(images, channel_names):
        fs, names = intensity_object_features(im, threshold=threshold,
                                              sample_size=sample_size,
                                              random_seed=random_seed)
        names = [prefix + '-' + name for name in names]
        all_fs.append(fs)
        all_names.extend(names)
    return np.concatenate(all_fs), all_names
