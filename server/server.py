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

from bottle import Bottle, run, request, template, redirect, route, abort
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

    # Variable used to display errors or who is the leader on the HTML page
    display_error = ""

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

            # When a vessel is unreachable
            # We are deleting this vessel from the vessel_list

            # Because we have only the value and not the key of the list, we have to make a for loop
            # The id is the key
            # The ip is the value
            id_to_delete = -1
            for id, ip in vessel_list.items():
                if str(ip) == str(vessel_ip): #we have found the key associated to the value
                    id_to_delete = id
                    break

            # We delete the faulty vessel
            del vessel_list[str(id_to_delete)]

            # Propagate to the others then they can update their list
            # We are giving node_id : the vessel will know from who the message comes
            # If it is ourself, we are stopping the propagate
            # The faulty id to delete : id_to_delete
            path = '/propagate/vesselCrashed/' + str(node_id) + '/' + str(id_to_delete)

            thread = Thread(target=propagate_to_neighbour, args=(path,))
            thread.deamon = True
            thread.start()

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

        # We are gonna propagating to the neighbour
        # We are using the list, and propagating to the node just after ourself

        next = 0
        neighbour_ip = -1   # we don't have a neighbour yet

        for id, ip in vessel_list.iteritems():
            if next == 1:                   # neighbour found
                neighbour_ip = ip
                break
            if int(id) == int(node_id):     # we have found ourself, the next node will be our neighbour
                next += 1

        # Because it is a ring, if we are the last one
        # the neighbour_ip is not set but next is assigned
        # the neighbour is the first in the list
        if next == 1 and neighbour_ip == -1:
            neighbour_ip = vessel_list.values()[0]

        # Debug prints
        # print "Propagating to " + str(neighbour_ip) + " with path:"
        # print path

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
        global board, node_id, display_error
        return template('server/index.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems()), members_name_string='Group Italia-French',
                        error = display_error)

    @app.get('/board')
    def get_board():
        global board, node_id
        print board
        return template('server/boardcontents_template.tpl', board_title='Vessel {}'.format(node_id),
                        board_dict=sorted(board.iteritems()), error = display_error)


    # ------------------------------------------------------------------------------------------------------

    @app.post('/board')
    def client_add_received():

        # Adds a new element to the board.
        # Called directly when a user sends a POST request on /board to a vessel. We are gonna contact the leader.
        # Called directly when a vessel or a user sends a POST request to the leader. It is adding the data to the board, assign an
        # id and propagate it to every nodes.

        global board, node_id, board_id, leader_id

        try:

            # The new entry is either in the form (if a user send it) or in the body of the request (if a vessel send it)
            # Indeed, it is either a user or a vessel who send the post request.
            if request.forms.get('entry') is not None:
                new_entry = request.forms.get('entry')      # if the form is completed, we get the entry from it
            else:
                new_entry = request.body.read()             # otherwise we get the entry in the body of the request

            # The vessel who receive the request is the leader
            if str(leader_id) == str(node_id):

                # We add new element to dictionary using board_id as entry sequence.
                add_new_element_to_store(str(board_id), new_entry)

                # Build path to propagate, using key word "add" and board_id as element_id.
                path = "/propagate/add/" + str(board_id)

                # Increment board_id for the next use of this function.
                board_id += 1

                # Start thread so the server doesn't make the client wait and propagate to all the vessles
                thread = Thread(target=propagate_to_vessels, args=(path, new_entry,))
                thread.deamon = True
                thread.start()

                return True

            # The vessel who receive the request is not the leader
            # We send the data to the leader
            else:

                # The same path
                path = "/board"

                # The ip address of the leader
                vessel_ip = vessel_list[str(leader_id)]

                thread = Thread(target=contact_vessel, args=(vessel_ip, path, new_entry,))
                thread.deamon = True
                thread.start()

                return True

        except Exception as e:
            print e

        return False


    @app.post('/board/<element_id:int>')
    def client_action_received(element_id):

        # Modify or delete an element in the board
        # Called directly when a user is doing a POST request on /board/<element_id:int>/ to a vessel. We contact the leader.
        # Called directly when a vessel or a user sends a POST request to the leader. It is modifying or deleting the data to the board, assign an
        # id and propagate it to every nodes.
        # element_id : the id of the element we want to modify or delete

        # Retrieving the ID of the action, which can be either 0 or 1.
        # 0 is received when the user clicks on "modify".
        # 1 is received when the user clicks on "delete".

        # Because it is either a user or a vessel who send the post request, we have to handle how the information arrive
        # If the form is completed, we get all the data from the form
        if request.forms.get('delete') is not None:
            delete = request.forms.get('delete')
            new_entry = request.forms.get('entry')

        # If the forms is empty, a vessel send the data
        else:
            new_entry = request.body.read()     # the data is in the body of the request

            if new_entry == "":                 # if there is nothing, that means we want to delete the data
                delete = "1"
            else:                               # if there is something, that means we want to modify the data
                delete = "0"


        if delete == "0":
            # User wants to modify entry with ID given by element_id.

            # If we are the leader, then we can change the data
            if str(leader_id) == str(node_id):
                # Modify the element in the dictionary
                modify_element_in_store(str(element_id), new_entry)

                # Build path to propagate using keyword "mod" which stands for "modify".
                path = "/propagate/mod/" + str(element_id)

                # Propagate the changes to all the vessels
                thread = Thread(target=propagate_to_vessels, args=(path, new_entry,))
                thread.deamon = True
                thread.start()

            # If we are not the leader, we send to the leader the modification we want to make
            else:
                # The same path, with the id of the element we want to modify
                path = "/board/" + str(element_id)

                # The ip of the leader
                vessel_ip = vessel_list[str(leader_id)]

                thread = Thread(target=contact_vessel, args=(vessel_ip, path, new_entry,))
                thread.deamon = True
                thread.start()

                return True

        elif delete == "1":
            # User wants to modify entry with ID given by element_id.

            # If we are the leader, then we can change the data
            if str(leader_id) == str(node_id):
                # User wants to delete entry with ID given by element_id.
                delete_element_from_store(entry_sequence=str(element_id))

                # Build path to propagate using keyword "del" which stands for "delete".
                path = "/propagate/del/" + str(element_id)

                # Propagate the changes to all the vessels
                thread = Thread(target=propagate_to_vessels, args=(path,))
                thread.deamon = True
                thread.start()

            # If we are not the leader, we send to the leader the modification we want to make
            else:
                # The same path, with the id of the element we want to delete
                path = "/board/" + str(element_id)

                # The ip of the leader
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

        pass


    @app.post('/propagate/<action>/<element_id>/<potential_leader>')
    def propagation_received_potential_leader(action, element_id, potential_leader):

        # Lab 2 propagation actions

        # Propagate action. An action is distinguished using one of the two keywords "findPotentialLeader", and "vesselCrashed"

        # - findPotentialLeader : is the leader election mecanism. It will use the ring to find the leader and when
        # his message will return it chooses his leader
        # element_id : the node from whom the message have begun. Thus, if a node receive a message
        # from itself, it will end.
        # potential_leader : the id of the potential_leader
        # request.body : the election_number of this potential leader

        # - vesselCrashed : is the way we are handling when a vessel is unreachable. Delete the vessel from the vessel_list
        # and start leader election if necessary
        # element_id : the node from whom the message have begun. Thus, if a node receive a message
        # from itself, it will end.
        # potential_leader : the id of the faulty vessel


        global election_number, node_id, leader_id, vessel_list, board, board_id, display_error

        # Leader election mecanism
        if action == "findPotentialLeader":

            #I am the initiator, I can finish the loop (the id of the message is ourself)
            if str(element_id) == str(node_id):

                # the potential_leader has passed through the whole ring, it is now the leader
                leader_id = potential_leader
                data = request.body.read()      #the election_number of the leader

                print "Leader is decided: " + str(leader_id)
                # Display it on the HTML page
                display_error = 'Leader : ' + str(leader_id) +", election_number : " + str(data)

                # In the case of a faulty node, and this one was the leader, we will have a new leader
                # Nevertheless, the board_id of the new leader is not updated
                # If we are the leader, we are updating the board_id
                if str(leader_id) == str(node_id):

                    # we will take the maximum id through the board
                    max = -1;
                    for id in board:
                        if max <= int(id):
                            max = int(id)

                    #the board_id is now coherent with the board already in all the nodes
                    board_id = max + 1

            # I am not the initiator, I elect a potential leader and pass to my neighbour
            else:

                # the election_number of the potential_leader
                data = request.body.read()

                # if this potential_leader has an election_number smaller than I, I am the new potential_leader
                if election_number > int(data):
                    potential_leader = node_id      # I am the new potential_leader
                    data = str(election_number)     # The data is now my election_number

                # if we have an equality
                elif election_number == int(data):
                    # we are taking the node with smallest id
                    # thus, everybody will have the same leader
                    if int(node_id) < int(potential_leader):
                        potential_leader = node_id

                # element_id : always the same, the initiator
                path = '/propagate/findPotentialLeader/' + str(element_id) + '/' + str(potential_leader)

                # We propagate to the neighbour the potential_leader and his election number
                thread = Thread(target=propagate_to_neighbour, args=(path, data))
                thread.deamon = True
                thread.start()

        # Handle if a vessel is not responding
        if action == "vesselCrashed":

            # I am not the initiator of the message. I delete the faulty vessel and propagate it
            if str(element_id) != str(node_id) :
                # delete the vessel unreachable
                del vessel_list[str(potential_leader)]

                # element_id : initiator of the request
                # potential_leader : vessel_id of the vessel unreachable
                path = '/propagate/vesselCrashed/' + str(element_id) + '/' + str(potential_leader)

                # propagate to my neighbour
                thread = Thread(target=propagate_to_neighbour, args=(path,))
                thread.deamon = True
                thread.start()

            # If the unreachable vessel is the leader, we have to update our leader
            if str(potential_leader) == str(leader_id):
                # We display an error message to the HTML page
                display_error = 'The server leader is down... We are sorry but the message is lost. Wait a few seconds to find a new leader.'

                # We begin a leader_election again
                thread = Thread(target=leader_election)
                thread.deamon = True
                thread.start()

        pass

    # ------------------------------------------------------------------------------------------------------
    # LEADER ELECTION FUNCTION
    # ------------------------------------------------------------------------------------------------------

    def get_random_id():
        # Get a random int to set the election_number.

        n_servers = len(vessel_list)
        # We are setting the random between 1 and a large number.
        # We set the beginning to 1 to distinguished the servers : all the server with a id equal to 0 are
        # not-initialized.
        # We multiply the number of servers by 50 to have a large random number and minimize the chances of 2 servers
        # having the same ID.

        election_number_tmp = randint(1, n_servers * 50)
        return election_number_tmp


    def leader_election():
        # We launch the leader election mecanism.

        global election_number

        # We wait 1 second before launching the leader election. Indeed, the server may have not be initialized yet.
        time.sleep(1)

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

        # We set the election_number before doind any leader_election
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
