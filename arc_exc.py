import datetime
import dill
import json
import math
import numpy as np
import os
import sys
sys.path.append('./dreamcoder/')
import pickle
import random
import signal
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
import subprocess
import csv
import json

#from dreamcoder.utilities import eprint, flatten, testTrainSplit, lse, runWithTimeout, pop_all_domain_specific_args
#from dreamcoder.grammar import Grammar, ContextualGrammar
from dreamcoder.task import Task
from dreamcoder.type import Context, arrow, tbool, tlist, tint, t0, UnificationFailure
from dreamcoder.program import Program
from dreamcoder.domains.arc.arcPrimitives import *


example={"input": [[0, 9, 9, 5], [0, 4, 0, 0], [0, 4, 0, 0], [0, 0, 0, 0]], "output": [[0, 2, 8, 2], [0, 8, 0, 0], [0, 2, 0, 0], [0, 0, 0, 0]]}

class ArcTask(Task):
    def __init__(self, name, request, examples, evalExamples, features=None, cache=False, sentences=[]):
        super().__init__(name, request, examples, features=features, cache=cache)
        self.evalExamples = evalExamples
        self.sentences = sentences

    def checkEvalExamples(self, e, timeout=None):
        if timeout is not None:
            def timeoutCallBack(_1, _2): raise EvaluationTimeout()
        try:
            signal.signal(signal.SIGVTALRM, timeoutCallBack)
            signal.setitimer(signal.ITIMER_VIRTUAL, timeout)

            try:
                f = e.evaluate([])
            except IndexError:
                # free variable
                return False
            except Exception as e:
                eprint("Exception during evaluation:", e)
                return False

            for x, y in self.evalExamples:
                if self.cache and (x, e) in EVALUATIONTABLE:
                    p = EVALUATIONTABLE[(x, e)]
                else:
                    try:
                        p = self.predict(f, x)
                    except BaseException:
                        p = None
                    if self.cache:
                        EVALUATIONTABLE[(x, e)] = p
                if p != y:
                    if timeout is not None:
                        signal.signal(signal.SIGVTALRM, lambda *_: None)
                        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
                    return False

            return True
        # except e:
            # eprint(e)
            # assert(False)
        except EvaluationTimeout:
            eprint("Timed out while evaluating", e)
            return False
        finally:
            if timeout is not None:
                signal.signal(signal.SIGVTALRM, lambda *_: None)
                signal.setitimer(signal.ITIMER_VIRTUAL, 0)

def taskMessage(t,p):
    m = {
        "examples": [{"inputs": [xs[0].toJson()], "output": y.toJson()} for xs, y in t.examples],
        "name": t.name,
        "request": t.request.json(),
        "programs": [p]
    }
    return m

# def execute_programs(tasks, grammar, task_to_programs):

#     message = {
#         "tasks": [taskMessage(t, task_to_programs) for t in tasks],
#         "programTimeout": 0.1,
#     }
#     dumped_message = json.dumps(message)
#     with open('message', 'w') as outfile:
#         json.dump(message, outfile) 

#     try:
#         solver_file = "./solvers/exec_arc_p"
#         process = subprocess.Popen(
#             solver_file, stdin=subprocess.PIPE, stdout=subprocess.PIPE
#         )
#         response, error = process.communicate(bytes(dumped_message, encoding="utf-8"))
        
#         response = json.loads(response.decode("utf-8"))
#         return response
        
#     except OSError as exc:
#         raise exc

def exc_program(taskname,example,program):
    trainExamples = [
                        ((Grid(gridArray=example["input"]),), Grid(gridArray=example["output"]))
                    ]
    task = ArcTask(
        taskname,
        arrow(tgridin, tgridout),
        trainExamples,
        None
    )
    message = {
        "tasks" : [taskMessage(task,program)],
        "programTimeout": 0.1,
    }
    dumped_message = json.dumps(message)
    # with open('message', 'w') as outfile:
    #     json.dump(message, outfile) 
    try:
        solver_file = "./solvers/exec_arc_p"
        process = subprocess.Popen(
            solver_file, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        response, error = process.communicate(bytes(dumped_message, encoding="utf-8"))
        response = json.loads(response.decode("utf-8"))
        #print('response',response)
        return response
    except OSError as exc:
        raise exc

if __name__ == "__main__":
    task1_path = "./arc_data/data/training"
    task2_path = "./arc_data/data/evaluation"
    program_path = "./data/arc/all_programs_nl_paragraphs.csv"
    write_path = "./all_program_check.csv"
    write_file = open(write_path,"w")
    writer = csv.writer(write_file)
    writer.writerow(["task","program","pass"])
    reader = csv.reader(open(program_path,'r'))
    total_num = 0
    pass_num = 0
    non_pass_p = set()
    for row in reader:
        taskname = row[0]
        program = row[1]
        flag = True
        if os.path.exists(task1_path+"/"+taskname):
            f = open(task1_path+"/"+taskname,"rb")
            examples = json.load(f)
            f.close()
            for example in examples["train"]+examples["test"]:           
                response = exc_program(taskname,example,program)
                loglike = response[0]["log_likelihoods"][0]
                print(loglike)
                if loglike != 0.0:
                    print(taskname)
                    print(example["input"])
                    print(example["output"])
                    flag = False
        elif os.path.exists(task2_path+"/"+taskname):
            f = open(task2_path+"/"+taskname,"rb")
            examples = json.load(f)
            f.close()
            for example in examples["train"]+examples["test"]:           
                response = exc_program(taskname,example,program)
                loglike = response[0]["log_likelihoods"][0]
                print(loglike)
                if loglike != 0.0:
                    print(taskname)
                    print(example["input"])
                    print(example["output"])
                    flag = False
        else:
            print("no task")
            continue
        total_num += 1
        if flag:
            pass_num += 1
        else:
            non_pass_p.add(program)
        writer.writerow([taskname,program,flag])
    print("total_num",total_num)
    print("pass_num",pass_num)
    print("non_pass_p",len(non_pass_p),non_pass_p)


        
