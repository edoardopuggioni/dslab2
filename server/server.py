# coding=utf-8

# ------------------------------------------------------------------------------------------------------

# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID

# Students:
# - Edoardo Puggioni
# - Jean-Nicolas Winter

# ------------------------------------------------------------------------------------------------------

import traceback
import sys
import time
import json
import argparse
from threading import Thread
from random import randint

from bottle import Bottle, run, request, template
import requests

# ------------------------------------------------------------------------------------------------------

try:
    app = Bottle()

    # Dictionary to store all entries of the blackboard.
    board = {}

    # Variable to know the next board_id to use for each new entry.
    board_id = 0

    # Random variable sets at the beginning to decide which server is gonna be the leader.
    leaderElection_number = 0

    # Variable of the leader_id of the set
    leader_id = 0

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------

    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):

        global board, node_id
        success = False

        try:
            # Simply add new element to the dictionary using entry_sequence as index.
            board[entry_sequence] = element
            success = True

        except Exception as e:
            print e

        return success


    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call=False):

        global board, node_id
        success = False

        try:
            # Modify dictionary element using entry_sequence as index.
            board[entry_sequence] = modified_element
            success = True

        except Exception as e:
            print e

        return success


    def delete_element_from_store(entry_sequence, is_propagated_call=False):

        global board, node_id
        success = False

        try:
            # Delete dictionary element using entry_sequence as index.
            del board[entry_sequence]
            success = True

        except Exception as e:
            print e

        return success


    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload=None, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
            # result is in res.text or res.json()
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success


    def propagate_to_vessels(path, payload=None, req='POST'):
        global vessel_list, node_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id:  # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)


    def propagate_to_neighbour(path, payload=None, req='POST'):
        global vessel_list, node_id

        numberServer = len(vessel_list)
        neighbourID = (node_id % (numberServer)) + 1
        neighbourIP = vessel_list[str(neighbourID)]

        success = contact_vessel(str(neighbourIP), path, payload, req)
        if not success:
            print "\n\nCould not contact neighbour \n\n"


    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for post
    # ------------------------------------------------------------------------------------------------------

    @app.route('/')
    def index():
        global board, node_id
        return template('server/index.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems()), members_name_string='Group Italia-French')

    @app.get('/board')
    def get_board():
        global board, node_id
        print board
        return template('server/boardcontents_template.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems()))

    # ------------------------------------------------------------------------------------------------------
    @app.post('/board')
    def client_add_received():

        # Adds a new element to the board
        # Called directly when a user is doing a POST request on /board

        global board, node_id, board_id, leader_id

        try:

            if request.forms.get('entry') != None:
                new_entry = request.forms.get('entry')
            else :
                new_entry = request.body.read()

            if str(leader_id) == str(node_id):
                # We add new element to dictionary using board_id as entry sequence.
                add_new_element_to_store(str(board_id), new_entry)

                # Build path to propagate, using key word "add" and board_id as element_id.
                path = "/propagate/add/" + str(board_id)

                # Increment board_id for the next use of this function.
                board_id += 1

                # Start thread so the server doesn't make the client wait.
                thread = Thread(target=propagate_to_vessels, args=(path, new_entry,))
                thread.deamon = True
                thread.start()
                return True
            else :
                path = "/board"
                vessel_ip = vessel_list[str(leader_id)]

                thread = Thread(target=contact_vessel, args=(vessel_ip, path, new_entry,))
                thread.deamon = True
                thread.start()
                return True

        except Exception as e:
            print e

        return False


    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):

        # Modify or delete an element in the board
        # Called directly when a user is doing a POST request on /board/<element_id:int>/

        # Retrieving the ID of the action, which can be either 0 or 1.
        # 0 is received when the user clicks on "modify".
        # 1 is received when the user clicks on "delete".

        if request.forms.get('delete') != None:
            delete = request.forms.get('delete')
            new_entry = request.forms.get('entry')
        else :
            new_entry = request.body.read()
            if new_entry == "":
                delete = "1"
            else:
                delete = "0"


        if delete == "0":
            if str(leader_id) == str(node_id):
                # User wants to modify entry with ID given by element_id.
                modify_element_in_store(str(element_id), new_entry)

                # Build path to propagate using keyword "mod" which stands for "modify".
                path = "/propagate/mod/" + str(element_id)

                thread = Thread(target=propagate_to_vessels, args=(path, new_entry,))
                thread.deamon = True
                thread.start()
            else :
                path = "/board/" + str(element_id) + "/"
                vessel_ip = vessel_list[str(leader_id)]

                thread = Thread(target=contact_vessel, args=(vessel_ip, path, new_entry,))
                thread.deamon = True
                thread.start()
                return True

        elif delete == "1":
            if str(leader_id) == str(node_id):
                # User wants to delete entry with ID given by element_id.
                delete_element_from_store(entry_sequence=str(element_id))

                # Build path to propagate using keyword "del" which stands for "delete".
                path = "/propagate/del/" + str(element_id)

                thread = Thread(target=propagate_to_vessels, args=(path,))
                thread.deamon = True
                thread.start()
            else :
                path = "/board/" + str(element_id) + "/"
                vessel_ip = vessel_list[str(leader_id)]

                thread = Thread(target=contact_vessel, args=(vessel_ip, path,))
                thread.deamon = True
                thread.start()
                return True

        pass


    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):

        global board_id, node_id, leader_id

        # Propagate action. An action is distinguished using one of the three keywords "add", "mod" and "del", which
        # stand for add, modify and delete respectively. After identifying the action, we identify the entry to
        # add/modify/delete by using the variable element_id, and also in the case of add and modify, the new entry can
        # be retrieved from the body of the POST request.

        if action == "add":
            # If we are the leader_id we retrieve the new entry from the body of the POST request.

            entry = request.body.read()
            add_new_element_to_store(element_id, entry)


        if action == "mod":
            # We retrieve the new entry from the body of the POST request.

            entry = request.body.read()
            modify_element_in_store(element_id, entry)


        if action == "del":

            delete_element_from_store(entry_sequence=element_id)

        if action == "notLeader":
            print "not leader ACTIVATED WARNING WWARNING !"

        if action == "isLeader":
            leader_id = element_id
            print "THE LEADER : " + str(leader_id)

        pass

    @app.post('/propagate/<action>/<element_id>/<potentialLeader>')
    def propagation_received_potential_Leader(action, element_id, potentialLeader):

        global leaderElection_number, node_id, leader_id

        if action == "findPotentialLeader":
            if str(element_id) == str(node_id): #I am myself, I can stop and decide of the leaderElection
                print "THE LEADER : " + str(potentialLeader)
                leader_id = potentialLeader
                path = '/propagate/isLeader/' + str(leader_id)

                thread = Thread(target=propagate_to_vessels, args=(path,))
                thread.deamon = True
                thread.start()
            else:
                data = request.body.read()

                if leaderElection_number > int(data):
                    potentialLeader = node_id
                    data = str(leaderElection_number)

                path = '/propagate/findPotentialLeader/' + str(element_id) + '/' + str(potentialLeader)
                thread = Thread(target=propagate_to_neighbour, args=(path, data))
                thread.deamon = True
                thread.start()
        pass


    # ------------------------------------------------------------------------------------------------------
    # LEADER ELECTION FUNCTION
    # ------------------------------------------------------------------------------------------------------
    def getRandomID():
        numberServer = len(vessel_list)
        #We are setting the random between 1 and a large number.
        #We set the beginning to 1 to distinguished the servers : all the server with a id equal to 0 are not-initialized
        #We multiply the number of servers by 100 to have a large random number and minimize the chances of 2 servers having the same ID.
        leaderElection_number = randint(1, numberServer * 100)
        return leaderElection_number

    def leaderElection():
        global leaderElection_number

        time.sleep(1)
        print "starting leader Election"
        path = '/propagate/findPotentialLeader/' + str(node_id) + '/' + str(node_id)
        propagate_to_neighbour(path,str(leaderElection_number))

        return True;


    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    # Execute the code
    def main():
        global vessel_list, node_id, app, leaderElection_number

        port = 80
        #port = 8080
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int,
                            help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))
            #vessel_list[str(i)] = '127.0.0.{}'.format(str(i))

	    leaderElection_number = getRandomID()

        if str(node_id) == "1":
            thread = Thread(target=leaderElection)
            thread.deamon = True
            thread.start()

        try:
            run(app, host=vessel_list[str(node_id)], port=port)

        except Exception as e:
            print e


    # ------------------------------------------------------------------------------------------------------
    if __name__ == '__main__':
        main()

except Exception as e:
    traceback.print_exc()
    while True:
        time.sleep(60.)
