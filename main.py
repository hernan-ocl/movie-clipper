# Press ⌃R to execute in PyCharm.
# In terminal run it with the command
#   python main.py
#   or also with arguments:
#   python main.py path_to_json path_to_movie_file
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.

# All the imports here
import json
import sys
from moviepy.editor import *

# Global variables here
verbose = True
json_path = 'Resources/data.json'
movie_path = 'Resources/sample_1h19m.mp4'
testing_time_threshold = 120
clip_time_before = 3
clip_time_after = 3
clip_time_no_success_before = 3
clip_time_no_success_after = 6
result_movie_format = "Output/Clip_{0}_{1}_{2}_{3}.mp4"


# Functions here
def parse_json(path):
    print("Reading json data file at '" + path + "'")
    # Read the file and parse the json into data
    with open(path, 'r') as file:
        data = json.load(file)
    # Output:
    if verbose:
        print(json.dumps(data, indent=4, sort_keys=True))

    return data


def format_to_time(time):
    day = time // (24 * 3600)
    time = time % (24 * 3600)
    hour = time // 3600
    time %= 3600
    minutes = time // 60
    time %= 60
    seconds = time
    formatted_time = "h:m:s-> %d:%d:%d" % (hour, minutes, seconds)
    if verbose:
        print(formatted_time)
    return formatted_time


# Classes
class ClipData:
    start_time = 0
    end_time = 0
    success = False

    def __init__(self, _start_time, _end_time, _success):
        self.start_time = _start_time
        self.end_time = _end_time
        self.success = _success

    def duration(self):
        return self.end_time - self.start_time


class PlayerMovieData:
    nfc_id = ""
    name = ""
    clips = []

    def __init__(self, _id, _name, _clips):
        self.nfc_id = _id
        self.name = _name
        self.clips = _clips


# FirstScan is inputted manually by the person who is in editing the video.
# This is a way to calibrate the log with the actual video file. So for example, if the FirstScan was 2000,
# that means with the actual video that was received, the first scan happened at 2000 seconds, and we would
# take the earliest TestingTimes which let's say is 183 seconds, and match that up with the actual start of
# the video at 2000 seconds. Does that make sense? It should be possible for FirstScan to also be smaller
# than the earliest TestingTimes. We currently don't network our camera, which means we can't control when it
# starts recording in our class exactly.
# Otherwise, the data should be pretty self-explanatory. TestingTimes is when each kid scans their wristband.
# SuccessTimes is when the teacher hits success.
# I think the first version of the application for the output can be rather simple. Taking this JSON file and a video,
# output a series of videos keyed on NfcId. Each video will contain all clips of the kid, and we will use a
# generous algorithm of either:
# If there is a SuccessTimeA within 120 seconds of the TestingTimeA, clip TestingTimeA - 30s to SuccessTimeA + 30s
# If there is no SuccessTime within 120 seconds of a TestingTimeB, simply clip TestingTimeB - 30s  to TestingTimeB + 60s
if __name__ == '__main__':
    # handle arguments, if any
    arguments_count = len(sys.argv)
    if verbose:
        print(">>>>> Program arguments: " + str(sys.argv))
    if arguments_count >= 2 and sys.argv[1] != "":
        json_path = sys.argv[1]
    if arguments_count == 3:
        movie_path = sys.argv[2]

    raw_data = parse_json(json_path)
    initial_offset = int(raw_data["FirstScan"])
    log_list = raw_data["Log"]
    if verbose:
        print("Initial offset {}".format(initial_offset))
        print("Log list is {}".format(log_list))

    movie_clips_data_list = []
    # for each element in the list, we need to gather the clips times
    for d in log_list:
        nfc_id = d["NfcId"]
        name = d["Name"]
        if verbose:
            print(">> Checking timings for '{1}' (id:{0})".format(nfc_id, name))

        interactions = d["TestingTimes"]
        if len(interactions) <= 0:
            print("No TestingTimes for kid '{0}' with id '{1}'. Impossible to get a clip.".format(name, nfc_id))
            continue

        for i in interactions:
            is_success = False
            successes = d["SuccessTimes"]
            if len(successes) > 0:
                interaction_clips = []
                # Check if there are success inside the expected time
                for s in successes:
                    start = i - clip_time_before
                    end = s + clip_time_after
                    threshold = (i + testing_time_threshold)
                    if threshold >= s > start:
                        if verbose:
                            print("Interaction time {}, success {}, start {} to {}".format(i, s, start, end))
                        is_success = True
                        if verbose:
                            print(">> is inside time expected {}".format(i, s, threshold))
                        cd = ClipData(start, end, True)
                        interaction_clips.append(cd)
                    else:
                        is_success = False
                        # TODO: Use a function for all this logic
                        start = i - clip_time_no_success_before
                        end = i + clip_time_no_success_after
                        if verbose:
                            print(">> Interaction time {}, NO SUCCESS!, start {} end {}".format(i, start, end))
                        cd = ClipData(start, end, False)
                        interaction_clips.append(cd)
                # rof
                # Add the clips to the list, so it can be generated later
                if len(interaction_clips) > 0:
                    pmd = PlayerMovieData(nfc_id, name, interaction_clips)
                    movie_clips_data_list.append(pmd)
            # this is kind-of an else:
            if not is_success and len(successes) <= 0:
                # No successes? then just clip a range from the testing time (interaction)
                start = i - clip_time_no_success_before
                end = i + clip_time_no_success_after
                if verbose:
                    print("Interaction time {}, NO SUCCESS!, start {} end {}".format(i, start, end))
                cd = ClipData(start, end, False)
                pmd = PlayerMovieData(nfc_id, name, [cd])
                movie_clips_data_list.append(pmd)
            # esle
        # rof
    # rof

    if verbose:
        # print("These are the movie clips: {}".format(movie_clips_data_list))
        print("Amount of clips to generate: {}".format(len(movie_clips_data_list)))

    # Load the full movie
    movie = VideoFileClip(movie_path)
    counter = 1
    for pmd in movie_clips_data_list:
        for cd in pmd.clips:
            start_time = initial_offset + cd.start_time
            end_time = initial_offset + cd.end_time
            success_flag = "success"
            if not cd.success:
                success_flag = "no_success"
            movie_path_result = result_movie_format.format(pmd.nfc_id, pmd.name, counter, success_flag)
            if verbose:
                print("Cutting clip from {0} to {1} (duration: {2})".format(start_time,
                                                                            end_time,
                                                                            format_to_time(cd.duration())))
                print("Writing video file at {0}".format(movie_path_result))
            clip = movie.subclip(start_time, end_time)
            clip.write_videofile(movie_path_result, codec="libx264", audio_codec="aac")
            counter = counter + 1
        # rof
    # rof

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
