# Module to generate logs for server load testing
import argparse
import os
import re
import sys
import json
import random
import string
import uuid
import time
from datetime import date, timedelta, datetime
from collections import OrderedDict

g_version = '1.0'
 
def parse_arguments():
    global g_version
    args = argparse.ArgumentParser(description = 'Log Generator v%s' % g_version)
    args.add_argument('-log', '--logfile', required=True)
    args.add_argument('-data', '--datavalues', required=True)
    args.add_argument('-s_date', '--start_date', default=str(date.today() - timedelta(days=7)))
    args.add_argument('-e_date', '--end_date', default=str(date.today()))
    args.add_argument('-live', '--live', action='store_true')
    args.add_argument('-hours', '--hours', type=float, default=0)
    args.add_argument('-mins', '--minutes', type=float, default=30)
    args.add_argument('-up_spike', '--spike_max_time', type=int, default=500)
    args.add_argument('-down_spike', '--spike_min_time', type=int, default=300) 
    args.add_argument('-max_day', '--max_per_day', type=int, default=100)
    args.add_argument('-min_day', '--min_per_day', type=int, default=25)
    args.add_argument('-max_sec', '--max_per_second', type=int, default=50)
    args.add_argument('-min_sec', '--min_per_second', type=int, default=25)
    args.add_argument('-v', '--version', action='version', version="%s %s" % (sys.argv[0], g_version))
    return args.parse_args()

def read_log_lines(logfile):
    '''To return the set of log lines as a list from the given log file'''
    with open(logfile, 'r') as log:
        return log.readlines()

def read_data_values(datavalues):
    with open(datavalues, 'r') as data_file:    
        return json.load(data_file)
	
def get_variable_list(line):
    '''To return all the variables in the given log line'''
    return re.findall("{{\w+}}", line)

def json_file_validation(logs, json_values):
    '''To validate the input json file'''
    missing_values = []
    for line in logs:
        var = get_variable_list(line)
        for item in var:
            if (item.replace('{{','').replace('}}','') not in json_values.keys()):
                missing_values.append(item.replace('{{','').replace('}}',''))
    missing_values = list(set(missing_values))
    if ("date" in missing_values):
        missing_values.remove("date")
    return missing_values
    
def generate_skeleton(args):
    '''Generate skeleton will create a dictionary with date as the key and number of logs
       for that day as value'''
    skeleton = OrderedDict()
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    d = end_date - start_date
    for i in xrange(d.days):
        #To limit the number of logs generated per day and have variable number of transactions each day.
        skeleton[start_date + timedelta(days=i)] = random.randrange(args.min_per_day, args.max_per_day + 1)
    return skeleton
        

def flow_ctx_generator(size=24, chars=string.ascii_uppercase + string.digits):
    '''Generate a flowcontext of the given length'''
    return ''.join(random.choice(chars) for _ in range(size))

            
def generate_line(date, hour, line, data_values):
    '''Generate each log line for the given parameters'''
    value_dict = {}
    variables = get_variable_list(line)
    value_dict['date'] = date.strftime('%Y/%m/%d')
    value_dict['hour'] = str(hour).zfill(2)
    for data in variables:
        data = data.replace('{{','').replace('}}','')
        if (data != 'date') and (data != 'hour') and (data in data_values.keys()) and (data not in value_dict.keys()):
            if data_values[data]['type'] == 'integer':
                value_dict[data] = random.randrange(int(data_values[data]['min']), int(data_values[data]['max'])+1)
            if data_values[data]['type'] == 'uuid':
                value_dict[data] = flow_ctx_generator(size=data_values[data]['length'])
            if data_values[data]['type'] == 'string':
                value_dict[data] = random.choice(str(data_values[data]['selection']).split(','))
    try : 
        value_dict["mts"] = str(value_dict["mts"]).zfill(2)
        value_dict["sec"] = str(value_dict["sec"]).zfill(2)
        value_dict["msec"] = str(value_dict["msec"]).zfill(3)
    except:
        pass
    for value in value_dict.keys():
        var_word = '{{' + str(value) + '}}'
        line = line.replace(var_word, str(value_dict[value])).rstrip()
    return line

			
def get_logs_per_hour(hours_list, log_count):
    '''Given the total logs and the allowed "hour" values for each line, this function computes number of log lines to be associated with each "hour"'''
    percent = {}
    hours = {}
    for i in hours_list:
        hours[i] = 0
    for i in xrange(100):
        h = random.choice(hours_list)
        if (h not in percent.keys()):
            percent[h] = 1
        else :
	    percent[h] = percent[h] + 1
    for hour, perc in percent.iteritems():
        hours[hour] = int((perc * log_count)/100)+ random.randrange(2)
    return hours


def generate_logs(args, skeleton, logs, json_values):
    '''Generate logs based on skeleton'''
    log_data = {}
    hours_list = range(int(json_values['hour']['min']), int(json_values['hour']['max'])+1)
    hours = {}
    for sdate, count in skeleton.iteritems():
         log_count = 0
         hours = get_logs_per_hour(hours_list, count)
         #To generate logs in chronological order
         hours_list.sort()
         pos = 0
         while (log_count < count):
             if hours[hours_list[pos]] >= 0:
                 hour = hours_list[pos]
                 hours[hours_list[pos]] -= 1
             else :
                 if (pos < len(hours_list) - 1):
                     pos += 1 
             flag = False
             while not flag:
                 logline = random.choice(logs)
                 if len(logline) > 1:
                     flag = True
             line = generate_line(date=sdate, hour=hour, line=logline, data_values=json_values) 
             print line
             log_count += 1



def generate_live_logs(args, skeleton, logs, json_values):
    '''Simulating the live generation of logs
       spike_max_time and spike_min_time are used to generate high and low spikes respectively in the logging. '''
    logs = read_log_lines(args.logfile)
    json_values = read_data_values(args.datavalues)
    timeout = int(60*60*args.hours) + int(60*args.minutes)
    spike_max_time = random.randrange(args.spike_max_time, args.spike_max_time + random.randrange(1,args.spike_max_time+5))
    spike_min_time = random.randrange(args.spike_min_time, args.spike_min_time + random.randrange(1,args.spike_min_time+5))
    while (timeout > 0):
        max_logs = random.randrange(args.min_per_second,args.max_per_second + 1)
        if (spike_max_time <= 0):
            max_logs = random.randrange(5*args.max_per_second, 10*args.max_per_second)
            spike_max_time = random.randrange(args.spike_max_time, (args.spike_max_time + random.randrange(1,args.spike_max_time+5)))
        elif (spike_min_time <= 0):
            max_logs = random.randrange(int(0.2*args.min_per_second), int(0.5*args.min_per_second))
            spike_min_time = random.randrange(args.spike_min_time, (args.spike_min_time + random.randrange(1,args.spike_min_time+5)))
        with open("log-count",'a') as f:
            f.write("Time :%s"%str(timeout))
            f.write("\tLogs :%s"%str(max_logs))
            f.write("\n")
        for i in xrange(max_logs):
            sdate = random.choice(skeleton.keys())
            hour = random.randrange(int(json_values['hour']['min']), int(json_values['hour']['max'])+1)
            flag = False
            while not flag:
                logline = random.choice(logs)
                if len(logline) > 1:
                    flag = True
            line = generate_line(date=sdate, hour=hour, line=logline, data_values=json_values)
            print line
        time.sleep(1)
        spike_max_time -= 1
        spike_min_time -= 1
        timeout -= 1


def main():
    args = parse_arguments()
    skeleton = generate_skeleton(args)
    logs = read_log_lines(args.logfile)
    json_values = read_data_values(args.datavalues)

    missing_values = json_file_validation(logs, json_values)
    if (len(missing_values) > 0):
        print "Missing Values in the Json Values :",missing_values
        sys.exit('Exiting!')
        
    if (args.live):
        generate_live_logs(args, skeleton, logs, json_values)
    else :       
        generate_logs(args, skeleton, logs, json_values)
           
	
if __name__ == '__main__':
    main()	

