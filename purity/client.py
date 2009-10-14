#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# The Purity library for Pure Data dynamic patching.
#
# Copyright 2009 Alexandre Quessy
# <alexandre@quessy.net>
# http://alexandre.quessy.net
#
# Purity is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Purity is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the gnu general public license
# along with Purity.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Simpler FUDI sender.
"""
import sys
import os
from twisted.internet import reactor
from twisted.internet import defer
from purity import fudi
from purity import server
from purity import process

VERBOSE = True

class PurityClient(object):
    """
    Dynamic patching Pure Data message sender.
    Used for dynamic patching with Pd.
    """
    # TODO: connect directly to pd-gui port, which is 5400 + n
    def __init__(self, receive_port=14444, send_port = 15555, use_tcp=True, quit_after_message=False, pd_pid=None):
        self.send_port = send_port
        self.receive_port = receive_port
        self.client_protocol = None
        self.fudi_server = None
        self.use_tcp = use_tcp # TODO
        self.quit_after_message = quit_after_message
        self._server_startup_deferred = None
        self.pd_pid = pd_pid # maybe None

    def register_message(self, selector, callback):
        """
        Registers a listener for a message selector.
        The selector is how we call the first atom of a message.
        An atom is a word. Atoms are separated by the space character.

        :param selector: str
        :param callback: callable
        @see purity.fudi.FUDIServerFactory.register_message
        """
        if self.fudi_server is not None: # TODO: more checking
            self.fudi_server.register_message(selector, callback)

    def start_purity_receiver(self):
        # TODO: rename to start_purity_receiver
        """ 
        You need to call this before launching the pd patch! 
        returns deferred
        """
        self._server_startup_deferred = defer.Deferred()
        self.fudi_server = fudi.FUDIServerFactory()
        self.fudi_server.register_message("__pong__", self.on_pong)
        self.fudi_server.register_message("__ping__", self.on_ping)
        self.fudi_server.register_message("__confirm__", self.on_confirm)
        self.fudi_server.register_message("__first_connected__", self.on_first_connected)
        self.fudi_server.register_message("__connected__", self.on_connected)
        print("reactor.listenTCP %d %s" % (self.receive_port, self.fudi_server))
        reactor.listenTCP(self.receive_port, self.fudi_server)
        #return self.fudi_server
        # TODO: add a timeout to this callback
        return self._server_startup_deferred

    def start_purity_sender(self):
        # TODO: rename to start_purity_sender
        """ 
        Starts purity sender. 
        returns deferred 
        """
        self.client_protocol = None
        if VERBOSE:
            print("Starting Purity/FUDI sender to port %d" % (self.send_port))
        deferred = fudi.create_FUDI_client('localhost', self.send_port, self.use_tcp)
        deferred.addCallback(self.on_client_connected)
        deferred.addErrback(self.on_client_error)
        return deferred

    def on_pong(self, protocol, *args):
        """ 
        Receives FUDI __pong__
        """
        print "received __pong__", args
        # print("stopping reactor")
        # reactor.stop()

    def on_ping(self, protocol, *args):
        """ 
        Receives FUDI __ping__
        """
        if VERBOSE:
            print "received __ping__", args

    def on_confirm(self, protocol, *args):
        """ 
        Receives FUDI __confirm__ for the confirmation of every FUDI message sent
        to Pure Data. You need to send Pure Data a "__enable_confirm__ 1" message.
        """
        if VERBOSE:
            print "received __confirm__", args

    def on_first_connected(self, protocol, *args):
        """ 
        Receives FUDI __first_connected__ when the Pure Data application 
        is ready and can send FUDI message to Python.
        """
        if VERBOSE:
            print "received __first_connected__", args
        self._server_startup_deferred.callback(self.fudi_server)
    
    def on_connected(self, protocol, *args):
        """ 
        Receives FUDI __connected__ when the Pure Data application 
        connects or re-connects after a disconnection.
        """
        if VERBOSE:
            print "received __connected__", args

    def on_client_connected(self, protocol):
        """ 
        Client can send messages to Pure Data 
        """
        self.client_protocol = protocol
        # self.client_protocol.send_message("ping", 1, 2.0, "bang")
        # print "sent ping"
        return protocol # pass it to the next

    def on_client_error(self, failure):
        """ 
        Client cannot send data to pd 
        """
        print "Error trying to connect.", failure
        raise Exception("Could not connect to pd.... Dying.")
        # print "stop"
        # reactor.stop()
    
    def quit(self):
        """
        Quits server and client.
        :return deferred:
        """
        deferred = defer.Deferred()
        def _kill_server(deferred):
            try:
                sig = 9
                os.kill(self.pd_pid, sig)
                mess = "Killed Pure Data successfully."
            except OSError, e:
                mess = "Pure Data quit successfully."
            deferred.callback(mess)
        self.send_message("pd", "quit")

        if self.pd_pid is not None:
            reactor.callLater(0.5, _kill_server, deferred)
        return deferred

    def send_message(self, selector, *args):
        """ 
        Send a message to pure data 
        """
        if self.client_protocol is not None:
            if VERBOSE:
                print("Purity sends %s %s" % (selector, str(args)))
            # if fudi.VERBOSE:
            # print("sending %s" % (str(args)))
            # print args[0], args[1:]
            # args = list(args[1:])
            # atom = args[0]
            # print("will send %s %s" % (selector, args))
            # self.client_protocol.send_message(*args, selector)
            self.client_protocol.send_message(selector, *args)
        else:
            print("Could not send %s" % (str(args)))
        if self.quit_after_message:
            print "stopping the application"
            # TODO: try/catch
            reactor.callLater(0, reactor.stop)

    def create_patch(self, patch):
        """
        Sends the creation messages for a subpatch.
        """
        mess_list = patch.get_fudi() # list of (fudi) lists
        # print(mess_list)
        for mess in mess_list:
            if VERBOSE:
                print("%s" % (mess))
            self.send_message(*mess)

#def create_patch(fudi_client, patch):
#    """
#    Sends the creation messages for a subpatch.
#    DEPRECATED. Use client.create_patch(patch) instead.
#    """
#    mess_list = patch.get_fudi() # list of (fudi) lists
#    # print(mess_list)
#    for mess in mess_list:
#        if VERBOSE:
#            print("%s" % (mess))
#        fudi_client.send_message(*mess)

#def _create_forked_client(**server_kwargs):
#    # technique 1: using fork and exec
#    # TODO: receive message from pd to know when it is really ready.
#    def _client_started(protocol, my_deferred, the_client):
#        """
#        Called when purity received __first_connected__
#        """
#        print("_client_started")
#        print("trigger callback %s %s" % (my_deferred, the_client))
#        my_deferred.callback(the_client)
#        return True
#
#    def _server_started(the_server, my_deferred, the_client):
#        """
#        called when pd and purity are connected.
#        """
#        print("_server_started")
#        # the_server is useless here.
#        c_deferred = the_client.start_purity_sender() # start it
#        c_deferred.addCallback(_client_started, my_deferred, the_client)
#
#    my_deferred = defer.Deferred()
#    pid = server.fork_and_start_pd(**server_kwargs)
#    if pid != 0:
## FIXME: we should start_purity_server prior to launch pd !
#        the_client = PurityClient(
#            receive_port=15555, 
#            send_port=17777, 
#            quit_after_message=False, 
#            pd_pid=pid,
#            use_tcp=True) # create the client
#        s_deferred = the_client.start_purity_receiver() # triggered when it receives __on_first_connected__
#        s_deferred.addCallback(_server_started, my_deferred, the_client)
#        return s_deferred
#    else:
#        sys.exit(0) # do not do anything else here !

def _create_managed_client(**server_kwargs):
    """
    Purity startup using the Process manager.
    
    1. Creates a Purity receiver... waits for __on_first_connected__ message.
    2. Launches Pure Data using the ProcessManager class.
    3. On loadbang, it receives the __on_first_connected__ message
    4. It then starts the Purity sender and callback its main deferred.

    Returns a Deferred.
    """
    # technique 2: using a process protocol. (much better)
    def _eb_sender_error(reason, my_deferred):
        print("Could not start purity sender: %s" % (reason.getErrorMessage()))
        my_deferred.errback(reason)
        #return reason #propagate error

    def _cb_sender_started(protocol, my_deferred, the_client):
        """
        Called when purity received __first_connected__
        """
        print("purity sender started")
        my_deferred.callback(the_client)
        #return the_client # pass client to next deferred.
    
    #def _eb_manager_err(reason, my_deferred):
    #    print("Could not start Pure Data process manager: %s" % (reason.getErrorMessage()))
    #    my_deferred.errback(reason)
    #    #return reason #propagate error

    #def _cb_manager_started(result, my_deferred, purity_client):
    #    """
    #    called when pd and purity are connected.
    #    """
    #    print(" purity _receiver_started %s %s %s" % (result, my_deferred, purity_client))
    #    # the_server is useless here.
    #    pd_server = result
    #    c_deferred = purity_client.start_purity_sender() # start the fudi sender. should trigger its callback quite quickly is a [netreceives] is listening
    #    c_deferred.addCallback(_cb_sender_started, my_deferred, purity_client)
    #    c_deferred.addErrback(_eb_sender_error, my_deferred)

    #def _cb_receiver_started(result, my_deferred, purity_client):
    #    print("purity receiver started")
    #    my_deferred = defer.Deferred()
    #    manager_deferred = server.run_pd_manager(**server_kwargs)
    #    manager_deferred.addCallback(_cb_manager_started, my_deferred)
    #    manager_deferred.addErrback(_eb_manager_err, my_deferred)
    #
    #def _eb_receiver_error(reason, my_deferred, purity_client):
    #    print("Could not start purity receiver: %s" % (reason.getErrorMessage()))
    #    my_deferred.errback(reason)
    # function body -------
    
    def _cb_both_started(result, my_deferred, purity_client):
        print("Both Pure Data patch and Purity listener are started.")
        sender_deferred = purity_client.start_purity_sender() 
        # start the fudi sender. should trigger its callback 
        # quite quickly is a [netreceives] is listening
        sender_deferred.addCallback(_cb_sender_started, my_deferred, purity_client)
        sender_deferred.addErrback(_eb_sender_error, my_deferred, purity_client)
    def _eb_both_error(reason, my_deferred, purity_client):
        my_deferred.errback(reason)

    # ------------------------------
    my_deferred = defer.Deferred()
    purity_client = PurityClient(
        receive_port=15555, 
        send_port=17777, 
        quit_after_message=False) # create the client
    print("created purity client: %s" % (purity_client))
    print("starting purity receiver")
    receiver_deferred = purity_client.start_purity_receiver() 
    #TODO: start_listener()
    #TODO : wait a bit here using a callLater ?
    manager_deferred = server.run_pd_manager(**server_kwargs) 
    # result will be PureData instance. (with a _process_manager attribute)
    # but we do not care for now.
    dl = [receiver_deferred, manager_deferred]
    d = process.deferred_list_wrapper(dl)
    d.addCallback(_cb_both_started, my_deferred, purity_client)
    d.addErrback(_eb_both_error, my_deferred, purity_client)
    # ... my_deferred will be triggered when all is done. 
    return my_deferred


#def create_simple_client(**server_kwargs):
#    """
#    Creates a purity server (Pure Data process manager)
#    and a purity client. 
#    """
#    USE_MANAGER = True
#    #USE_MANAGER = False # XXX important 
#    # technique 1: using fork and exec
#    if not USE_MANAGER:
#        return _create_forked_client(**server_kwargs)
#    else:
#        return _create_managed_client(**server_kwargs)

def create_client(**pd_kwargs):
    """
    New version of create_simple_client, but using 
    the managed process. Its deferred results in a purity client.
    :return: Deferred.
    """
    return _create_managed_client(**pd_kwargs)

create_simple_client = create_client # alias

