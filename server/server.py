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
    election_number = 0

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

        global vessel_list, node_id

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

            id_to_delete = -1
            for id, ip in vessel_list.items():
                if str(ip) == str(vessel_ip):
                    id_to_delete = id
                    break
            del vessel_list[str(id_to_delete)]

            path = '/propagate/vesselCrashed/' + str(node_id) + '/' + str(id_to_delete)

            thread = Thread(target=propagate_to_neighbour, args=(path,))
            thread.deamon = True
            thread.start()

            return template('server/index.tpl', board_title='Vessel {}'.format(node_id),
                            board_dict=sorted(board.iteritems()), members_name_string='Group Italia-French', error='The leader is down... The message is lost, wait a few seconds to find a new leader.')

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

        next = 0
        neighbour_ip = -1

        for id, ip in vessel_list.iteritems():
            if next == 1:
                neighbour_ip = ip
                break
            if int(id) == int(node_id):
                next += 1
        if next == 1 and neighbour_ip == -1:
            neighbour_ip = vessel_list.values()[0]

        # Debug prints
        print "Propagating to " + str(neighbour_ip) + " with path:"
        print path

        success = contact_vessel(str(neighbour_ip), path, payload, req)
        if not success:
            print "Could not contact neighbour"


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

        # Adds a new element to the board.
        # Called directly when a user is doing a POST request on /board.

        global board, node_id, board_id, leader_id

        try:

            if request.forms.get('entry') is not None:
                new_entry = request.forms.get('entry')

            else:
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

            else:

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

        if request.forms.get('delete') is not None:
            delete = request.forms.get('delete')
            new_entry = request.forms.get('entry')
        else:
            new_entry = request.body.read()
            if new_entry == "":
                delete = "1"
            else:
                delete = "0"

        if delete == "0":
            # User wants to modify entry with ID given by element_id.

            if str(leader_id) == str(node_id):
                modify_element_in_store(str(element_id), new_entry)

                # Build path to propagate using keyword "mod" which stands for "modify".
                path = "/propagate/mod/" + str(element_id)

                thread = Thread(target=propagate_to_vessels, args=(path, new_entry,))
                thread.deamon = True
                thread.start()

            else:

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
            else:
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

        # Lab 1 propagation actions

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

        # --------------------------------------------------------------------------------------------------------------

        # Leader election propagation

        if action == "notLeader":
            print "not leader ACTIVATED WARNING WARNING !"

        if action == "isLeader":

            leader_id = element_id
            print "Leader decision received: " + str(leader_id)

            if str(element_id) == str(node_id):
                # Propagation of leader decision is finished, I can stop
                return

            else:
                path = '/propagate/isLeader/' + str(leader_id)
                thread = Thread(target=propagate_to_neighbour, args=(path,))
                thread.deamon = True
                thread.start()

        pass


    @app.post('/propagate/<action>/<element_id>/<potential_leader>')
    def propagation_received_potential_leader(action, element_id, potential_leader):

        global election_number, node_id, leader_id, vessel_list

        if action == "findPotentialLeader":
            if str(element_id) == str(node_id):

                # I am the initiator, I can stop and decide the leader
                leader_id = potential_leader

                print "Initiator: leader is decided: " + str(leader_id)

                #path = '/propagate/isLeader/' + str(leader_id)
                #thread = Thread(target=propagate_to_neighbour, args=(path,))
                #thread.deamon = True
                #thread.start()

            else:

                # I am not the initiator of this election

                data = request.body.read()

                if election_number > int(data):
                    potential_leader = node_id
                    data = str(election_number)
                elif election_number == int(data):
                    if int(node_id) < int(potential_leader):
                        potential_leader = node_id

                path = '/propagate/findPotentialLeader/' + str(element_id) + '/' + str(potential_leader)
                thread = Thread(target=propagate_to_neighbour, args=(path, data))
                thread.deamon = True
                thread.start()
        if action == "vesselCrashed":

            print "\n****************************************"
            print "[DEBUG] The vessel crashed :" + potential_leader
            print "****************************************\n"

            if str(element_id) != str(node_id) :
                del vessel_list[str(potential_leader)]

                path = '/propagate/vesselCrashed/' + str(element_id) + '/' + str(potential_leader)

                thread = Thread(target=propagate_to_neighbour, args=(path,))
                thread.deamon = True
                thread.start()

            if str(potential_leader) == str(leader_id):
                thread = Thread(target=leader_election)
                thread.deamon = True
                thread.start()

        pass

    # ------------------------------------------------------------------------------------------------------
    # LEADER ELECTION FUNCTION
    # ------------------------------------------------------------------------------------------------------
    def get_random_id():
        n_servers = len(vessel_list)
        # We are setting the random between 1 and a large number.
        # We set the beginning to 1 to distinguished the servers : all the server with a id equal to 0 are
        # not-initialized.
        # We multiply the number of servers by 100 to have a large random number and minimize the chances of 2 servers
        # having the same ID.

        election_number_tmp = randint(1, n_servers * 100)
        return election_number_tmp


    def leader_election():

        global election_number

        time.sleep(2)

        print "Starting leader election"
        #                                          initiator_node       potential_leader
        path = '/propagate/findPotentialLeader/' + str(node_id) + '/' + str(node_id)
        propagate_to_neighbour(path, str(election_number))

        return True


    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    # Execute the code

    def main():

        global vessel_list, node_id, app, election_number

        port = 80
        # port = 8080
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
            # vessel_list[str(i)] = '127.0.0.{}'.format(str(i))

        election_number = get_random_id()
        print "I got election_number=" + str(election_number) + "\n"

        # Every node initiates leader election
        thread = Thread(target=leader_election)
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
