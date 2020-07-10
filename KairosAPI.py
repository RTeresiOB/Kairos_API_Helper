#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 15 12:28:40 2020

Send in urls of pictures to Kairos Face detect API and return .csv with face analysis.

@author: Leilah Harouni and Robert K Teresi
"""

# Import libraries
import concurrent.futures  # Execute multiple threads and return results
# import multiprocessing  # Maybe split threads into different cores
import pandas as pd  # Hold data in dataframe
import requests  # Send request to API
import json  # Parse json returned by API
from pathlib import Path  # OOP Paths
from datetime import datetime  # Keep track of when requests sent to API
from datetime import timedelta  # Add minute delay between requests
import pause  # Easy pausing until scheduled requests
import time

# Kairos API info/keys
api_url = "https://api.kairos.com"
app_id = "APP_ID_HERE"
app_key = "APP_KEY_HERE"


# Working Directory
DIRECTORY = Path(Path.home() / "PATH/TO/DIRECTORY")
inputfilename = DIRECTORY / 'TwitterImageUrls.csv'

outputfilename = DIRECTORY / "KairosDetectOutput.csv"

# Chunk size -- number of simultaneous requests to API
CHUNK_SIZE = 400  # Staying slightly under max allowed of 500

# Column names
column_names = ['image_id', 'image_url',
           'n_faces', 'age', 'gender',
           'asian', 'black', 'hispanic',
           'other', 'white', 'glasses']

def send_out_chunk(chunk):
    """Send out queued requests to api."""
    global begin, results
    # If our chunk is empty I am going to assume that the dataset ended on 
    # exactly when the last chunk was sent.
    if not chunk:
        return()  #  Nothing to send (Script should be over)
    print("Opening Pool Executor")
    begin = datetime.now()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(get_data_from_api,
                                   entry[0],entry[1])
                   for entry in chunk]
        concurrent.futures.wait(futures)
        results= list()
        n = 0
        for f in concurrent.futures.as_completed(futures):
            n += 1
            print("Parsing result " + str(n))
            try:
                results.append({key:item 
                                for key,item in zip(column_names, f.result())})  
            except:
                print("Result skipped ??")
                pass
    return(results)

def save_results(results):
    global out_data
    print("In Save function now.")
    for result in results:
        out_data = out_data.append(result,
                                   ignore_index = True)   
    print("Saving data.")
    # Now save dataframe
    out_data.to_csv(outputfilename,
                                index=False)
    print("Data. Saved.")
    print(str(len(chunk)) + " requests to API completed in " +
          str((datetime.now() - begin).seconds) + " seconds.")
    return(out_data)


def get_data_from_api(image_id=None,
                      image_url=None):
    """Send request to API and return data needdd for dataframe."""

    # Set API info
    api_url = "https://api.kairos.com/detect"

    headers = {
        'app_id': 'f5d84eb3',
        'app_key': 'e9dac7637898bb833d91a81eaf6e9832'
        } 

    payload = '{"image": "' + image_url + '"}'

    # Throw an error 
    if (not image_url) or (not image_id):
        Exception("Incomplete arguments to get_data_from_api given.")

    # Send request to api and format parse json
    r = requests.post(api_url, data=payload, headers=headers)
    j = json.loads(r.text)

    # If we don't have errors (face found) we return face stats
    if 'Errors' not in j:
        for face in j['images'][0]['faces']:
            #print(r.text)
            return([image_id, image_url, face['face_id'],
                      face['attributes']['age'],
                      face['attributes']['gender']['type'],
                      face['attributes']['asian'],
                      face['attributes']['black'],
                      face['attributes']['hispanic'],
                      face['attributes']['other'],
                      face['attributes']['white'],
                      face['attributes']['glasses']])

    # Otherwise return error codes and blank values
    else:
        print("No faces found/error occurred.")
        #print(r.text)
        return([image_id, image_url, j['Errors'][0]['ErrCode'],
                  j['Errors'][0]['Message'],
                  'ERR','ERR','ERR','ERR',
                  'ERR','ERR','ERR'])


def kairos_face_detect(inputfilename, outputfilename):
    global chunk
    """Execute main control flow."""
    global out_data, in_data
    
    # Initialize and assign wait_until to now
    wait_until = datetime.now()
    
    # Make dataframe if it is not already existing
    try:
        # If it exists this will work 
        out_data = pd.read_csv(outputfilename)
    except:
        # Amd if doesn't, then this will run and make an empty dataframe
        out_data = pd.DataFrame(columns=column_names)
    
    # Load input data
    in_data = pd.read_csv(inputfilename)

    for index, row in in_data.iterrows():
        '''
        We are going to utilize threading to approach the limit of our API
        subscription.
        
        We will iterate through the list of screen_names we have scraped,
        adding names to a chunk until we have 450 new and unique names (our
        limit is 500). Then, we will execute our get_data_from_api function,
        feeding in each url in a different thread. Since this is just an API
        request, I do not anticipate even 450 threads to overload the core.
        
        If it does we can split the threads between cores.
        '''
        
        # Initialize the "chunk" variable on our first entrance to the script
        try:
            chunk
        except NameError:
            chunk = list()  # Make chunk an empty list
        except:
            Exception("Unrecognized error while trying to call chunk variable.")

        # Only send data to the API that we  haven't already sent, or
        #   is not queued to be sent.
        if row['friend_screen_name'] in list(out_data['image_id']):
            print("Name already Found. Continuing.")
            print("Index: " + str(index))
            continue
        elif any(row['friend_screen_name'] in i for i in chunk):
            print("Name already in chunk. Continuing.")
            print("Index: " + str(index))
            continue
        # If we are less than our max, add a new element to chunk
        elif len(chunk) < (CHUNK_SIZE - 1):
            chunk.append([row['friend_screen_name'],
                          row['friend_image_url']])
            # Else if we are at the limit add the row and send the requests
            # if it is time to do so.
        else:
            chunk.append([row['friend_screen_name'],
                          row['friend_image_url']])
            try:
                # Pause.until automatically continues script once time has passed.
                print(wait_until)
                pause.until(wait_until)
                time.sleep(5)
                
            except NameError:
                # Set wait_until variable until a minute after requests made
                print(wait_until)
                wait_until = datetime.now() + timedelta(minutes=1)
            except Exception:
                Exception("Unknown error occurred while initializing wait_until")

            wait_until = datetime.now() + timedelta(minutes=1)
            out_data = save_results(send_out_chunk(chunk))
            chunk = list()

    # When we get all the way through the input df, we will probably have
    # a few entries still queued up. Send these out and then print that the
    # script has finished.
    pause.until(wait_until)
    send_out_chunk(chunk)
    print("Main function exiting. Script finished.")

if __name__ == '__main__':
    kairos_face_detect(inputfilename, outputfilename)
