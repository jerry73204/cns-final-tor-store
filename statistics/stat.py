#!/usr/bin/env python3
import os
import argparse
from collections import defaultdict
import statistics
from pprint import pprint

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
            bid = int(bid)
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
                if duration_stat[bid]['retrieve']:
                    prev_ts, _ = duration_stat[bid]['retrieve'][-1]
                    assert ts > prev_ts
                duration_stat[bid]['retrieve'].append((ts, False))

    # Compute success rates
    drop_count = 0
    fail_before_first_successful_retrieve = 0

    for bid, stat in duration_stat.items():
        if stat['address'] is None:
            drop_count += 1

        durations = list(
            (ts - stat['stored'], success)
            for ts, success in stat['retrieve']
        )

        success_count = 0
        fail_count = 0
        fail_count_after_first = 0
        success_rates = list()
        first_success_dur = None
        last_success_dur = None
        times_fail_to_first_successful_retrieve = None

        for dur, success in durations:
            if success:
                success_count += 1
                last_success_dur = dur
                if first_success_dur is None:
                    first_success_dur = dur
                    times_fail_to_first_successful_retrieve = fail_count
                    if fail_count > 0:
                        fail_before_first_successful_retrieve += 1
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

        stat['times_fail_to_first_successful_retrieve'] = times_fail_to_first_successful_retrieve
        stat['first_success_retrieve'] = first_success_dur
        stat['retrieve_stat'] = retrieve_stat
        stat['live_time'] = live_time

    # Live time histogram
    bin_width = 30.               # 30 minutes
    live_time_stat = list(
        stat['live_time'] / 60
        for bid, stat in duration_stat.items()
        if stat['live_time'] is not None
    )

    fig, axs = plt.subplots(1, 1, sharey=True, tight_layout=True)
    axs.hist(
        live_time_stat,
        bins=np.arange(0., max(live_time_stat) + bin_width, bin_width),
    )
    plt.savefig(os.path.join(args.output_dir, 'live_time_histogram.png'))

    # First success retrieve histogram
    bin_width = 1.
    first_success_retrieve_stat = list(
        stat['first_success_retrieve'] / 60
        for bid, stat in duration_stat.items()
        if stat['first_success_retrieve'] is not None
    )
    fig, axs = plt.subplots(1, 1, sharey=True, tight_layout=True)
    axs.hist(
        first_success_retrieve_stat,
        bins=np.arange(0., max(first_success_retrieve_stat) + bin_width, bin_width),
    )
    plt.savefig(os.path.join(args.output_dir, 'first_success_retrieve_histogram.png'))

    # Compute storing time
    store_time_stat = list(
        (stat['stored'] - stat['start']) / 60
        for bid, stat in duration_stat.items()
        if stat['stored'] is not None
    )

    # Print statistics
    num_blocks = len(duration_stat)
    drop_rate = drop_count / len(duration_stat)
    print(
        'drops:',
        '%d/%d' % (drop_count, num_blocks),
        '%f%%' % (drop_rate * 100),
        sep='\t',
    )
    print(
        'failed_before_retrieve:',
        '%d/%d' % (fail_before_first_successful_retrieve, num_blocks),
        '%f%%' % (fail_before_first_successful_retrieve * 100 / num_blocks)
    )
    print(
        'mean_store_time:',
        '%f mins' % statistics.mean(store_time_stat),
        sep='\t',
    )
    print(
        'mean_live_time:',
        '%f mins' % statistics.mean(live_time_stat),
        sep='\t',
    )


if __name__ == '__main__':
    main()
