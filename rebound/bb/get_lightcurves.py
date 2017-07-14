#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
import os
import time
import matplotlib.pyplot as plt
from scipy.ndimage.filters import gaussian_filter as gf
from scipy.ndimage import measurements as mm


# utilities
DATA_FILEPATH = os.path.join(os.environ['REBOUND_DATA'],'bb','2017')

def find_night(DATA_FILEPATH, night,step=100,plot=False):
    '''
    Extract files and plots avg luminosity. Assumes Brooklyn data.
    Upon click, prints file number (to indicate where to start loading)
    Upon release, prints file number (to indicate where to stop loading)
    Parameters:
    ___________
    data_dir = str
        full filepath of directory with images to be processed
        - requires RBG format

    step = int (default 100)
        indicates step size when iterating through files in data_dir

    plot = boolean (default False)
        if True, method will plot average luminosity (of each image) over time
        to allow for visual selection of optimal file start and stop

        if False, method will determine optimal start and stop analytically


    Returns:
    ________

    file_start,file_stop

    if plot = True, draws plot
    '''
    data_dir = os.path.join(DATA_FILEPATH, night)

    lum_list = []

    for i in sorted(os.listdir(data_dir))[::step]:
        lum_list.append(np.memmap(os.path.join(data_dir, i), dtype=np.uint8, mode='r'))
        lum_means = np.array(lum_list,dtype=np.float32).mean(1)

    if not plot: # crude analytical method
        thresh = np.median(lum_means)+0.5
        file_start = np.where(lum_means<thresh)[0][0]*step+step
        file_stop = np.where(lum_means<thresh)[0][-1]*step

        return file_start,file_stop

    else: # plot method

        def vline_st(event):
            if event.inaxes == ax:
                cind = int(event.xdata)

                ax.axvline(cind,color='g')
                   
                ax.set_title("File #: {0}".format(cind))

                fig.canvas.draw()

                print "File start: {}".format(cind*step) + 100

        def vline_end(event):
            if event.inaxes == ax:
                cind = int(event.xdata)

                ax.axvline(cind,color='r')
                   
                ax.set_title("File #: {0}".format(cind))

                fig.canvas.draw()

                print "File stop: {}".format(cind*step)

        # -- set up the plots
        fig,ax = plt.subplots(1,figsize=(15, 5))
        im = ax.plot(lum_means)

        fig.canvas.draw()
        # fig.canvas.mpl_connect("motion_notify_event", update_spec)
        fig.canvas.mpl_connect('button_press_event', vline_st)
        fig.canvas.mpl_connect('button_release_event', vline_end)
        plt.show()

def multi_night(DATA_FILEPATH, nights, step=100, plot = False):
    '''
    Pulls files from multiple nights.

    Nights is a list of sub-directories, each for a night containing raw image files.

    '''

    # for each night in list
    data_filepath = os.path.join(os.environ['REBOUND_DATA'])

        # truncate daylight images
        file_start,file_stop = find_night(data_dir,step=100,plot=False)




def create_mask(DATA_FILEPATH, nights, step, thresh, create_ts_cube, multi, file_start, file_stop, gfilter):
    '''
    Converts a series of raw images into a 2-D boolean mask array
    that indicates pixels that are highly correlated based on 
    changes in luminosity over time with their
    neighbors to the left or right, or above or below.
    Assumes Brooklyn data, i.e. raw files are 3072 by 4096 and in monochrome8 format

    Parameters:
    ___________
    DATA_FILEPATH= str
        full filepath of directory that contains subdirectoris of nights

    nights = list of str
        sub-directory of night(s) containing raw image files
        - requires RBG format

    step = int (default 6)
        indicates step size when iterating through files in data_dir

    thresh = float (default .50)
        threshold correlation coefficient value, below which all pixels are masked

    i_start = int (default None)
        index of files in source directory to start loading at 
        (remember only the half files are .raw and half .jpg-->ignored)

    i_stop = int (default None)
        index of files in source directory to stop loading

    gf = int (default None)
        if not None, implements a gaussian filter pass with sigma for time dimension set at this value


    Returns:
    ________
    2-d numpy array
        boolean array that expresses true for coordinates of pixels that are correlated
        with neighbors.
    '''
    start_mask = time.time()

    # optional to find start/stop file index
    if file_start is None:
        print "Finding night images..."

        file_start,file_stop = find_night(data_dir)
        end_night = time.time()
        print "Time to find night: {}".format(end_night-start_mask)

    start_extract = time.time()
    print "Extracting image files..."

    # load raw files
    sh = (3072, 4096)
    imgs_list = []

    for i in sorted(os.listdir(data_dir))[file_start:file_stop:step]:
        imgs_list.append(np.fromfile(os.path.join(
                data_dir, i), dtype=np.uint8).reshape(sh[0], sh[1]))
    imgs = np.array(imgs_list,dtype=np.float32)

    # slice off last row and col to match mask array
    img_cube = imgs[:, :-1, :-1].copy()

    time_extract = time.time()

    print "Time to extract data and calculate mean: {}".format(time_extract - start_extract)

    # run Gaussian filter (options)
    if gfilter is not None:
        print "Running Gaussian filter..."
        imgs_sm = gf(imgs, (gfilter, 0, 0))
        imgs = imgs - imgs_sm

    time_standard_st = time.time()
    print "Standardizing luminosity along time domain..."

    # subtract mean along nimg axis
    imgs -= imgs.mean(axis=0, keepdims=True)

    # divide by array of standard deviation for each pixel time series
    imgs /= imgs.std(axis=0, keepdims=True)

    # this will create nan values for zero division (pixels with
    # unchanging luminosity i.e. 0 st. dev)
    # boolean mask and set nan values to 0 for further operations
    img_idx = np.isnan(imgs)
    imgs[img_idx] = 0

    time_standard = time.time()
    print "Time to standardize: {}".format(time_standard-time_standard_st)

    print "Calculating correlation coefficients..."

    # matrix mult to get horizontal and vertical correlation
    corr_x = (imgs[:, :-1, :] * imgs[:, 1:, :]).mean(0)
    corr_y = (imgs[:, :, :-1] * imgs[:, :, 1:]).mean(0)

    # Creating a mask for all the pixels/sources with correlation greater than
    # threshold
    corr_mask_x = corr_x[:, :-1] > thresh
    corr_mask_y = corr_y[:-1, :] > thresh

    # Merging the correlation masks in left-right and top-down directions
    mask_array = corr_mask_x | corr_mask_y

    stop_mask = time.time()
    print "Time to create final image mask: {}".format(stop_mask-time_standard)
    print "Total create mask runtime: {}".format(stop_mask-start_mask)
    return mask_array, img_cube


def light_curve(DATA_FILEPATH, nights, output_dir=None, step=5, thresh=.50, create_ts_cube = False, multi= False, file_start=100, file_stop=2800, gfilter=None):
    '''
    Calls create_mask() and uses output to label pixels to unique light sources.
    Averages the luminosity among pixels of each light source
    to produce lightcurve for each source.


        # slice off last row and col to match mask array
    img_cube = imgs[:, :-1, :-1].copy()
    '''
    start = time.time()

    # create mask array
    mask_array, img_cube = create_mask(
        DATA_FILEPATH, nights, step, thresh, create_ts_cube, file_start, file_stop, gfilter)
    
    time_label = time.time()
    # measurements.label to assign sources
    labels, num_features = mm.label(mask_array.astype(bool))

    unique, counts = np.unique(labels, return_counts=True)

    print "Creating time series array..."
    source_ts = []

    for i in range(0, img_cube.shape[0]):
        src_sum = mm.sum(img_cube[i, :, :].astype(np.float32), labels, index=unique[1:])
        source_ts.append(src_sum.astype(np.float32)/counts[1:])

    # stack sequence of time series into 2-d array time period x light source
    ts_array = np.stack(source_ts)

    time_ts_array = time.time()
    print "Time to create time series array: {}".format(time_ts_array - time_label)
    
    # broadcast timeseries of light sources into original image array
    if create_ts_cube:
        print "Broadcasting times series array to pixel image coordinates..."

        ts_cube = np.zeros(img_cube.shape)
        for i in range(0,ts_cube.shape[1]):
            for j in range(0,ts_cube.shape[2]):
                if labels[i,j] !=0:
                    ts_cube[:,i,j] = ts_array[:,labels[i,j]-1]

        ts_cube = ts_cube.astype(np.float32)
        time_create_cube = time.time()
        print "Time to create time series cube: {}".format(time_create_cube - time_ts_array)

   
    if output_dir != None:
        time_output = time.time()
        print "Saving files to output..."

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # cube
        np.save(os.path.join(output_dir,'cube.npy'),img_cube)

        # mask
        np.save(os.path.join(output_dir,'mask.npy'),mask_array)

        # labels
        np.save(os.path.join(output_dir,'labels.npy'),labels)

        # curves
        np.save(os.path.join(output_dir,'lightcurves.npy'),ts_array)

        # curves_cube
        if create_ts_cube:
            np.save(os.path.join(output_dir,'lightcurves_cube.npy'),ts_cube)

        end = time.time()
        print "Time to save files to output: {}".format(end-time_output)
        print "Total runtime: {}".format(end - start)

    else:
        class output():

            def __init__(self):
                self.fpath = data_dir
                self.cube = img_cube
                self.mask = mask_array
                self.labels = labels
                self.unique = unique
                self.counts = counts
                self.curves = ts_array
                if create_ts_cube:
                    self.curves_cube = ts_cube

        end = time.time()
        print "Total runtime: {}".format(end - start)
        return output()




