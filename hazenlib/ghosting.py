import os
import sys

import numpy as np
import cv2 as cv

import hazenlib


def calculate_ghost_intensity(ghost, phantom, noise) -> float:
    """
    Calculates the ghost intensity using the formula from IPEM Report 112
    Ghosting = (Sg-Sn)/(Sp-Sn) x 100%

    Returns:    :float

    References: IPEM Report 112 - Small Bottle Method
                MagNET

    """

    if ghost is None or phantom is None or noise is None:
        raise Exception(f"At least one of ghost, phantom and noise ROIs is empty or null")

    if type(ghost) is not np.ndarray:
        raise Exception(f"Ghost, phantom and noise ROIs must be of type numpy.ndarray")

    ghost_mean = np.mean(ghost)
    phantom_mean = np.mean(phantom)
    noise_mean = np.mean(noise)

    if phantom_mean < ghost_mean or phantom_mean < noise_mean:
        raise Exception(f"The mean phantom signal is lower than the ghost or the noise signal. This can't be the case ")

    return 100 * (ghost_mean - noise_mean) / phantom_mean


def get_signal_bounding_box(array: np.ndarray):
    max_signal = np.max(array)
    signal_limit = max_signal * 0.5  # assumes phantom signal is at least 50% of the max signal inside the phantom
    signal = []
    for idx, voxel in np.ndenumerate(array):
        if voxel > signal_limit:
            signal.append(idx)

    signal_column = sorted([voxel[1] for voxel in signal])
    signal_row = sorted([voxel[0] for voxel in signal])

    upper_row = min(signal_row) - 1  # minus 1 to get the box that CONTAINS the signal
    lower_row = max(signal_row) + 1  # ditto for add one
    left_column = min(signal_column) - 1  # ditto
    right_column = max(signal_column) + 1  # ditto

    return left_column, right_column, upper_row, lower_row,


def get_signal_slice(bounding_box, slice_size=10):
    slice_radius = round(slice_size / 2)
    left_column, right_column, upper_row, lower_row  = bounding_box
    centre_row = upper_row + round((lower_row - upper_row) / 2)
    centre_column = left_column + round((right_column - left_column) / 2)

    idxs = (np.array(range(centre_column - slice_radius, centre_column + slice_radius), dtype=np.intp),
            np.array(range(centre_row - slice_radius, centre_row + slice_radius), dtype=np.intp)[:, np.newaxis])
    return idxs


def get_pe_direction(dcm):
    return dcm.InPlanePhaseEncodingDirection


def get_background_rois(dcm, signal_centre):

    background_rois = []

    if get_pe_direction(dcm) == 'ROW':  # phase encoding is left -right i.e. increases with columns
        if signal_centre[1] < dcm.Rows * 0.5:  # phantom is in top half of image
            background_rois_row = round(dcm.Rows * 0.75)  # in the bottom quadrant
        else:  # phantom is bottom half of image
            background_rois_row = round(dcm.Rows * 0.25)  # in the top quadrant
        background_rois.append((signal_centre[0], background_rois_row))

        if signal_centre[0] > round(dcm.Columns/2):
            # phantom is right half of image need 4 ROIs evenly spaced from 0->background_roi[0]
            gap = round(background_rois[0][0] / 4)
            background_rois = [(background_rois[0][0] - i * gap, background_rois_row) for i in range(4)]
        else:
            # phantom is left half of image need 4 ROIs evenly spaced from background_roi[0]->end
            gap = round((dcm.Columns - background_rois[0][0]) / 4)
            background_rois = [(background_rois[0][0] + i * gap, background_rois_row) for i in range(4)]

    else:  # phase encoding is top-down i.e. increases with rows (y-axis)
        if signal_centre[0] < dcm.Columns * 0.5:  # phantom is in left half of image
            background_rois_column = round(dcm.Columns * 0.75)  # in the right quadrant
        else:  # phantom is right half of image
            background_rois_column = round(dcm.Columns * 0.25)  # in the top quadrant
        background_rois.append((background_rois_column, signal_centre[1]))

        if signal_centre[1] >= round(dcm.Rows/2):
            # phantom is bottom half of image need 4 ROIs evenly spaced from 0->background_roi[0]
            gap = round(background_rois[0][1] / 4)
            background_rois = [(background_rois_column, background_rois[0][1] - i * gap) for i in range(4)]
        else:  # phantom is top half of image need 3 ROIs evenly spaced from background_roi[0]->end
            gap = round((dcm.Columns - background_rois[0][1]) / 4)
            background_rois = [(background_rois_column, background_rois[0][1] + i * gap) for i in range(4)]

    return background_rois


def get_background_slices(background_rois, slice_size=10):
    slice_radius = round(slice_size / 2)
    slices = [(np.array(range(roi[0]-slice_radius, roi[0]+slice_radius), dtype=np.intp)[:, np.newaxis], np.array(
        range(roi[1]-slice_radius, roi[1]+slice_radius), dtype=np.intp))for roi in background_rois]

    return slices


def get_eligible_area(signal_bounding_box, dcm, slice_radius=5):

    left_column, right_column, upper_row, lower_row = signal_bounding_box
    padding_from_box = 30  # pixels

    if get_pe_direction(dcm) == 'ROW':
        if left_column < dcm.Columns / 2:
            # signal is in left half
            eligible_columns = range(right_column + padding_from_box, dcm.Columns - slice_radius)
            eligible_rows = range(upper_row, lower_row)
        else:
            # signal is in right half
            eligible_columns = range(slice_radius, left_column - padding_from_box)
            eligible_rows = range(upper_row, lower_row)

    else:
        if upper_row < dcm.Rows / 2:
            # signal is in top half
            eligible_rows = range(lower_row + padding_from_box, dcm.Rows - slice_radius)
            eligible_columns = range(left_column, right_column)
        else:
            # signal is in bottom half
            eligible_rows = range(slice_radius, upper_row - padding_from_box)
            eligible_columns = range(left_column, right_column)

    return eligible_columns, eligible_rows


def get_ghost_slice(signal_bounding_box, dcm, slice_size=10):
    max_mean = 0
    max_index = (0, 0)
    slice_radius = round(slice_size/2)
    windows = {}
    arr = dcm.pixel_array

    eligible_columns, eligible_rows = get_eligible_area(signal_bounding_box, dcm, slice_radius)

    for idx, centre_voxel in np.ndenumerate(arr):
        if idx[0] not in eligible_columns or idx[1] not in eligible_rows:
            continue
        else:
            windows[idx] = arr[idx[0]-slice_radius:idx[0]+slice_radius, idx[1]-slice_radius:idx[1]+slice_radius]

    for idx, window in windows.items():
        if np.mean(window) > max_mean:
            max_mean = np.mean(window)
            max_index = idx

    return np.array(
        range(max_index[0] - slice_radius, max_index[0] + slice_radius), dtype=np.intp)[:, np.newaxis], np.array(
        range(max_index[1] - slice_radius, max_index[1] + slice_radius)
    )


def get_ghosting(dcm, plotting=False) -> dict:

    bbox = get_signal_bounding_box(dcm.pixel_array)
    signal_centre = [(bbox[0]+bbox[1])//2, (bbox[2]+bbox[3])//2]
    background_rois = get_background_rois(dcm, signal_centre)
    ghost_roi_slice = get_ghost_slice(bbox, dcm)
    ghost = dcm.pixel_array[ghost_roi_slice]
    phantom = dcm.pixel_array[get_signal_slice(bbox)]

    noise = np.concatenate([dcm.pixel_array[roi] for roi in get_background_slices(background_rois)])
    eligible_area = get_eligible_area(bbox, dcm)
    ghosting = calculate_ghost_intensity(ghost, phantom, noise)

    if plotting:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        x1, x2, y1, y2 = bbox

        img = hazenlib.rescale_to_byte(dcm.pixel_array)
        img = cv.rectangle(img.copy(), (x1, y1), (x2, y2), (255, 0, 0), 1)

        for roi in background_rois:
            #  slice_size = 10
            x1 = roi[0] - 5
            y1 = roi[1] - 5
            x2 = roi[0] + 5
            y2 = roi[1] + 5
            img = cv.rectangle(img.copy(), (x1, y1), (x2, y2), (255, 0, 0), 1)

        x1 = ghost_roi_slice[0].min()
        y1 = ghost_roi_slice[1].min()
        x2 = ghost_roi_slice[0].max()
        y2 = ghost_roi_slice[1].max()
        img = cv.rectangle(img.copy(), (x1, y1), (x2, y2), (255, 0, 0), 1)

        x1 = min(eligible_area[0])
        y1 = min(eligible_area[1])
        x2 = max(eligible_area[0])
        y2 = max(eligible_area[1])
        img = cv.rectangle(img.copy(), (x1, y1), (x2, y2), (255, 0, 0), 1)

        ax.imshow(img)
        return fig, ghosting

    return None, ghosting


def main(data: list, report=False) -> dict:

    results = {}
    # figures = []
    for dcm in data:
        key = f"{dcm.SeriesDescription}_{dcm.EchoTime}ms_NSA-{dcm.NumberOfAverages}"
        fig, results[f"{dcm.SeriesDescription.replace(' ', '_')}_{dcm.EchoTime}ms_NSA-{dcm.NumberOfAverages}"] = get_ghosting(dcm, report)
        fig.savefig(key + '.png')

    return {'ghosting': results}


if __name__ == "__main__":
    main([os.path.join(sys.argv[1], i) for i in os.listdir(sys.argv[1])])
