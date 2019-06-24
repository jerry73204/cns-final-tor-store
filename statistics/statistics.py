#!/usr/bin/env python3
import os
import argparse
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from matplotlib.ticker import PercentFormatter


def main():
    # Parse args
    script_dir = os.path.dirname(os.path.realpath(__file__))
    default_input_path = os.path.join(script_dir, 'duration300.txt')

    parser = argparse.ArgumentParser()
    parser.add_argument('--input-file', default=default_input_path)
    parser.add_argument('--output-dir', default='duration_statistics')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    duration_stat = defaultdict(
        lambda: {
            'start': None,       # Timestamp when start storing
            'stored': None,      # Timestamp when Onion address is responsed
            'address': None,     # Onion address
            'retrieve': list(),  # List of retrieving attemps in (timestamp, success)
            'first_success_retrieve': None,  # Timestamp when first retrieving occurs
            'retrieve_stat': None,           # List of (timestamp, success_count, fail_count, success_rate, success_rate_after_first_success_retrieve)
            'live_time': 0       # Time difference b/w last and first success retrieving
        }
    )

    # Load input file
    with open(args.input_file) as file_input:
        for line in file_input:
            values = line[:-1].split('\t')
            ts, bid, action = values[:3]
            ts = float(ts)

            if action == 'start':
                assert duration_stat[bid]['start'] is None
                duration_stat[bid]['start'] = ts

            elif action == 'stored':
                assert duration_stat[bid]['start'] is not None
                assert duration_stat[bid]['stored'] is None
                assert duration_stat[bid]['address'] is None
                duration_stat[bid]['stored'] = ts
                duration_stat[bid]['address'] = values[3]

            elif action == 'retrieved':
                assert duration_stat[bid]['start'] is not None
                assert duration_stat[bid]['stored'] is not None
                assert duration_stat[bid]['address'] is not None
                duration_stat[bid]['retrieve'].append((ts, True))

            elif action == 'failed to retrieve':
                assert duration_stat[bid]['start'] is not None
                assert duration_stat[bid]['stored'] is not None
                assert duration_stat[bid]['address'] is not None
                duration_stat[bid]['retrieve'].append((ts, False))

    # Compute success rates
    drop_count = 0

    for bid, stat in duration_stat.items():
        if stat['address'] is None:
            drop_count += 1

        durations = list(
            (ts - stat['start'], success)
            for ts, success in stat['retrieve']
        )

        success_count = 0
        fail_count = 0
        fail_count_after_first = 0
        success_rates = list()
        first_success_dur = None
        last_success_dur = None

        for dur, success in durations:
            if success:
                success_count += 1
                last_success_dur = dur
                if first_success_dur is None:
                    first_success_dur = dur
            else:
                fail_count += 1
                if first_success_dur is not None:
                    fail_count_after_first += 1

            success_rate = success_count / (success_count + fail_count)

            if success_count + fail_count_after_first > 0:
                success_rate_after_first = success_count / (success_count + fail_count_after_first)
            else:
                success_rate_after_first = None

            success_rates.append((success_count, fail_count, success_rate, success_rate_after_first))

        if last_success_dur is not None:
            assert first_success_dur is not None
            live_time = last_success_dur - first_success_dur
        else:
            live_time = None

        retrieve_stat = list(
            (ts, succ_count, fail_count, rate, rate_after_first)
            for (ts, _success), (succ_count, fail_count, rate, rate_after_first) in zip(durations, success_rates)
        )

        stat['first_success_retrieve'] = first_success_dur
        stat['retrieve_stat'] = retrieve_stat
        stat['live_time'] = live_time

    drop_rate = drop_count / len(duration_stat)

    # Live time diagrams
    n_bins = 20
    live_time_stat = list(
        stat['live_time'] / 60
        for bid, stat in duration_stat.items()
        if stat['live_time'] is not None
    )

    fig, axs = plt.subplots(1, 1, sharey=True, tight_layout=True)
    axs.hist(live_time_stat, bins=n_bins)
    plt.savefig('wtf.png')

    print(drop_rate)

if __name__ == '__main__':
    main()
