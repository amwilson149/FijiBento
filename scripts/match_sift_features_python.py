import sys
import os
import glob
import argparse
from subprocess import call
from bounding_box import BoundingBox
import json
import itertools
import utils
import math
import time

# common functions


def descriptor_distance(f1,f2):
    dist = 0
    desc1 = f1["descriptor"]
    desc2 = f2["descriptor"]
    l = min(len(desc1),len(desc2))
    for i in range(l):
            a = (desc1[i] - desc2[i])
            dist += a*a
    return math.sqrt(dist)



def match_multiple_sift_features(tilespecs, features, index_pairs, out_fname, overlap_fraction, ROD = 0.9, overlap_only = 0):
    # 1. Match *all or overlapping* features of each pair of tiles
    match_locations = []
    for idx1,idx2 in index_pairs:
        print("({0},{1})".format(idx1,idx2))
        ft1 = features[idx1]["mipmapLevels"]["0"]["featureList"]
        ft2 = features[idx2]["mipmapLevels"]["0"]["featureList"]
        print(overlap_only)
        # In case you want to look at only the points in the overlap region
        if (overlap_only==1):
            bbox1 = tilespecs[idx1]["bbox"] # Check to make sure this is correct
            bbox2 = tilespecs[idx2]["bbox"]
            fl1 = features[idx1]["mipmapLevels"]["0"]["featureList"]
            fl2 = features[idx2]["mipmapLevels"]["0"]["featureList"]
            xs1 = [0]
            ys1 = [0]
            xs2 = [0]
            ys2 = [0]
            print(type(xs1))
            sys.exit("testing")
            print(ys1)
            print(xs2)
            print(ys2)
            for m in range (len(fl1)):
                xs1 = xs1.append(fl1[m]["location"][0])
                ys1 = ys1.append(fl1[m]["location"][1])
            for n in range (len(fl2)):
                xs2 = xs2.append(fl2[n]["location"][0])
                ys2 = ys2.append(fl2[n]["location"][1])

            xs1[0],ys1[0],xs2[0],ys2[0] = None
            sys.exit("testing")
            # Find the overlap intervals
            xl1,xr1,yt1,yb1 = bbox1[0],bbox1[1],bbox1[2],bbox1[3]
            xl2,xr2,yt2,yb2 = bbox2[0],bbox2[1],bbox2[2],bbox2[3]
            ovl,ovr = xl2,xr1
            if xl1 > xl2:
                ovl,ovr = xl1,xr2
            ovt,ovb = yt2,yb1
            if yt1 > yt2:
                ovt,ovb = yt1,yb2
            # Add some extra to the intervals you're checking
            delovx = (ovr-ovl)*1./3 # Hard-coded to increase search region from 6% to 10% of a tile, from Alyssa's data, but only if they're offset in a given dimension
            delovy = (ovb-ovt)*1./3
            if xl1 != xl2:
                ovl -= delovx
                ovr += delovx
            if yt1 != yt2:
                ovt -= delovy
                ovb += delovy

            # Reduce both feature lists to only those in the overlap
            ft1in = ft1[(xs1 > ovl) and (xs1 < ovr) and (ys1 > ovt) and (ys1 < ovb)]
            ft2in = ft2[(xs2 > ovl) and (xs2 < ovr) and (ys2 > ovt) and (ys2 < ovb)]

        else:
            ft1in = ft1
            ft2in = ft2
            print("flag2")
            print(len(ft1in))
            print(len(ft2in))

        # ****Check that this works properly****

        for f1 in ft1in:
            time_start = time.clock()
            best = None
            best_d = sys.float_info.max
            second_best_d = sys.float_info.max

            for f2 in ft2in:
                d = descriptor_distance(f1,f2)
                if ( d < best_d ):
                    second_best_d = best_d
                    best_d = d
                    best = f2
                        
                elif ( d < second_best_d ):
                    second_best_d = d
            if (best != None and second_best_d < sys.float_info.max and (best_d/second_best_d) <ROD):
                match_locations.append(((f1["location"][0],f1["location"][1]),(best["location"][0],best["location"][1])))

        if (match_locations != None):
            delta_time = time.clock() - time_start
            print("Matches found for this tile pair. Time elapsed is {0} seconds.".format(delta_time))
                
        # Remove ambiguous matches (where a particular f2 has been found to be the best match for more than one f1)
        for i in range(len(match_locations)+1):
            amb = false
            m = match_locations[i]
            for j in range(i+1,len(match_locations)+1):
                n = match_locations[j]
                if (m == n):
                    amb = true
                    del match_locations[n]
            if (amb):
                del match_locations[m]



        
        output_list = {"imageUrl1":(tilespecs[idx1]["mipmapLevels"]["0"]["imageUrl"]),
                       "imageUrl2":(tilespecs[idx2]["mipmapLevels"]["0"]["imageUrl"]),
                       "matchLocations":match_locations}
        # What else do we need to put here? Change the script so that you can define the search space by the max displacement?
     
    # Write tile pair and matches to the outfile
    with open(out_fname, 'w') as outfile:
        json.dump(output_list, outfile, ensure_ascii=False)
        
    

def load_data_files(tile_file, features_file):
    tile_file = tile_file.replace('file://', '')
    with open(tile_file, 'r') as data_file:
        tilespecs = json.load(data_file)

    features_file = features_file.replace('file://', '')
    with open(features_file) as data_file:
        features = json.load(data_file)
    return tilespecs, {ft["mipmapLevels"]["0"]["imageUrl"] : idx for idx, ft in enumerate(features)}, features
    


def match_sift_features(tiles_file, features_file, out_fname, overlap_fraction = 0.1):

    tilespecs, feature_indices, features = load_data_files(tiles_file, features_file)

    # for k, v in feature_indices.iteritems():
    #     print k, v
    # TODO: add all tiles to a kd-tree so it will be faster to find overlap between tiles
    # TODO: limit searches for matches to overlap area of bounding boxes

    # iterate over the tiles, and for each tile, find intersecting tiles that overlap,
    # and match their features
    # Nested loop:
    #    for each tile_i in range[0..N):
    #        for each tile_j in range[tile_i..N)]
    indices = []
    for pair in itertools.combinations(tilespecs, 2):
        # if the two tiles intersect, match them
        bbox1 = BoundingBox.fromList(pair[0]["bbox"])
        bbox2 = BoundingBox.fromList(pair[1]["bbox"])
        if bbox1.overlap(bbox2):
            imageUrl1 = pair[0]["mipmapLevels"]["0"]["imageUrl"]
            imageUrl2 = pair[1]["mipmapLevels"]["0"]["imageUrl"]
            print "Sift of tiles: {0} and {1} will be matched.".format(imageUrl1, imageUrl2)
            idx1 = feature_indices[imageUrl1]
            idx2 = feature_indices[imageUrl2]
            indices.append((idx1, idx2))

    ROD = 0.9
    overlap_only = 1
    match_multiple_sift_features(tilespecs, features, indices, out_fname, overlap_fraction, ROD, overlap_only)


def main():
    # Command line parser

    overlap_fraction = 0.06 # Alyssa's data

    parser = argparse.ArgumentParser(description='Iterates over the tilespecs in a file, computing matches for each overlapping tile.')
    parser.add_argument('tiles_file', metavar='tiles_file', type=str,
                        help='the json file of tilespecs')
    parser.add_argument('features_file', metavar='features_file', type=str,
                        help='the json file of features')
    parser.add_argument('-o', '--output_file', type=str, 
                        help='an output correspondent_spec file, that will include the sift features for each tile (default: ./matches.json)',
                        default='./matches.json')

    args = parser.parse_args()

    match_sift_features(args.tiles_file, args.features_file, args.output_file, overlap_fraction)




if __name__ == '__main__':
    main()

