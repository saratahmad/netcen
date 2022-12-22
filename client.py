'''
This module defines the behaviour of a client in your Chat Application
'''
import sys
import getopt
import socket
import random
from threading import Thread
import os
import util
from queue import Queue


'''
Write your code inside this class.
In the start() function, you will read user-input and act accordingly.
receive_handler() function is running another thread and you have to listen
for incoming messages in this function.
'''

class Client:
    '''
    This is the main Client Class. 
    '''
    def __init__(self, username, dest, port, window_size):
        self.server_addr = dest
        self.server_port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(None)
        self.sock.bind(('', random.randint(10000, 40000)))
        self.name = username
        self.window = window_size
        self.qUeue = Queue(maxsize=0)
        self.message_string = Queue(maxsize=0)
    def start(self):
        '''
        Main Loop is here
        Start by sending the server a JOIN message.
        Waits for userinput and then process it
        '''
        #sends server a join request
        user_input = sys.argv[2] #saving the name
        self.start_packet()
        initial_msg = util.make_message("join", 1, self.name)
        if self.qUeue.get() == "ack":
            self.sending_chunks(initial_msg)

        while True:
            user_input = input()
            if user_input.split()[0] == 'msg':
                #emptying the queue before calling the function for accurate seq no
                yes = self.qUeue.empty()
                if yes == False:
                    while not self.qUeue.empty():
                        self.qUeue.get()
                self.message(user_input)
            elif user_input.split()[0] == 'quit':
                #calling the quit function
                self.quit(user_input)
            elif user_input.split()[0] == 'list':
                #emptying the queue before calling the function for accurate seq no
                yes = self.qUeue.empty()
                if yes == False:
                    while not self.qUeue.empty():
                        self.qUeue.get()
                #calling the quit function
                self.listt()
            elif user_input.split()[0] == "help":
                #calling help function
                self.help(user_input)
            elif user_input.split()[0] == "file":
                #emptying the queue before calling the function for accurate seq no
                yes = self.qUeue.empty()
                if yes == False:
                    while not self.qUeue.empty():
                        self.qUeue.get()
                #file sharing
                self.file_sharing(user_input)
            else:
                print("incorrect userinput format")

    def start_packet(self):
        end = 0
        #random number generated
        seq_no = random.randint(0, 1000)
        if end == 0:
            #making packet
            init_packet1 = util.make_packet("start", seq_no,)
            self.sock.sendto(init_packet1.encode("utf-8"), (self.server_addr, self.server_port))
        else:
            end = 0

    def win_send(self, siz_win, seq_num, list_f):
        for i in range(0, siz_win):
            mess = util.make_packet("data", seq_num+i, list_f[i])
            self.sock.sendto(mess.encode("utf-8"), (self.server_addr, self.server_port))
            packet_route = i
        #returning the index
        return packet_route

    def sending_chunks(self, initial_msg):
        retry = 0
        #length of list
        list_f = self.make_chunks(initial_msg)
        seq_num = int(self.qUeue.get())#sequence number
        list_len = len(list_f) #length of list
        if (list_len < util.WINDOW_SIZE):#determining size of window to traverse the chunks list
            siz_win = list_len
        else:
            siz_win = util.WINDOW_SIZE
        packet_route = self.win_send(siz_win, seq_num, list_f)
        packet_route = packet_route + 1
        while(packet_route < list_len):
            try: 
                if self.qUeue.get(block = True, timeout= util.TIME_OUT) == "ack":
                    #comparing the acks received with the expected sequence numnber
                    val1 = int(self.qUeue.get())
                    if val1 == (int(seq_num) + 1):
                        #sliding the window acks sending the next 
                        message = util.make_packet("data", int(seq_num + packet_route), list_f[packet_route])
                        self.sock.sendto(message.encode("utf-8"), (self.server_addr, self.server_port))
                        packet_route = packet_route + 1
                seq_num = seq_num + 1
            except:
                #sending packets for retransmission                                                                              
                if (retry <= util.NUM_OF_RETRANSMISSIONS):
                    self.win_send(siz_win, seq_num, list_f)
                    retry = retry + 1
                else:
                    seq_num = seq_num + 1
        # sends the end packet, ending the connection
        self.qUeue.get()
        vall = int(self.qUeue.get())
        #making packet
        end_packet = util.make_packet("end", vall,)
        self.sock.sendto(end_packet.encode("utf-8"), (self.server_addr, self.server_port))
        # gets from the queue to remove the ack and sequence number of end packet

    def make_chunks(self, initial_packet):
        n = util.CHUNK_SIZE
        chunks = [initial_packet[i:i+n] for i in range(0, len(initial_packet), n)]
        return chunks

    def file_sharing(self, user_input):
        #extracting information from user input
        cmd_input = user_input.split()
        name_of_file = cmd_input[-1]
        filee = open(name_of_file, 'r')
        file_contents = filee.read()
        no_of_clients = cmd_input[1]
        clients_list = cmd_input[2:-1]
#concatenating the client list
        str_clients = ""
        for names in clients_list:
            str_clients = str_clients + names + " "
        str_clients = str_clients[:-1]
        data = no_of_clients + " " + str_clients + " " + name_of_file + " " + file_contents
#making packets to send file
        new_message = util.make_message("send_file", 4, data)
        self.start_packet()
        if self.qUeue.get() == "ack":
            self.sending_chunks(new_message)
    def message(self, user_input):
        self.start_packet()
        new_message = util.make_message("send_message", 4, user_input[3:])
        if self.qUeue.get() == "ack":
            self.sending_chunks(new_message)

    def help(self, user_input):
        print("possible user inputs: ")
        print("msg <number_of_users> <username1> <username2> ... <message>")
        print("list")
        print("file <number_of_users> <username1> <username2> ... <file_name>")
        print("help")
        print("quit")

    def listt(self):
        #start packet sent
        self.start_packet()
        new_message = util.make_message("request_users_list", 2)
        if self.qUeue.get() == "ack":
            self.sending_chunks(new_message)

    def quit(self, user_input):
        print("quitting")
        new_message = util.make_message("disconnect", 1, user_input)
        self.start_packet()
        if self.qUeue.get() == "ack":
            self.sending_chunks(new_message)
        sys.exit()
    def receive_handler(self):
        '''
        Waits for a message from server and process it accordingly
        '''
        bool_check = True
        while bool_check:
            message, address = self.sock.recvfrom(4096) #message recieved
            address_port = address[1]
            msg = ""
            decoded_message = message.decode("utf-8")
            parsed_message = util.parse_packet(decoded_message)
            if parsed_message[0] == "ack":
                #acks and seq numbers stored in queue
                self.qUeue.put(parsed_message[0])
                self.qUeue.put(parsed_message[1])

            if parsed_message[0] == "data":
                #recieving data packet and sending ack
                self.message_string.put(parsed_message[2])
                msg_packet = util.make_packet("ack", int(parsed_message[1])+1,)
                self.sock.sendto(msg_packet.encode("utf-8"), (self.server_addr, self.server_port))

            if parsed_message[0] == "start":
                #recieving start packet and sending ack
                init_seq_num = int(parsed_message[1]) + 1
                init_packet1 = util.make_packet("ack", init_seq_num,)
                self.sock.sendto(init_packet1.encode("utf-8"), (self.server_addr, self.server_port))

            if parsed_message[0] == "end":
                msg_packet = util.make_packet("ack", int(parsed_message[1])+1,)
                self.sock.sendto(msg_packet.encode("utf-8"), (self.server_addr, self.server_port))
                if bool_check == True: #concatnating the message
                    while not self.message_string.empty():
                        msg = msg + self.message_string.get()
                else:
                    break
                if msg.split()[0] == "forward_message":
                    #calling forward function
                    self.forward_message(msg)
                elif msg.split()[0] == "response_users_list":
                    self.response_users_list(msg)
                elif msg.split()[0] == "err_server_full":
                    print("disconnected: server full")
                    sys.exit()
                elif msg.split()[0] == "err_username_unavailable":
                    print("disconnected: username not available")
                    sys.exit()
                elif msg.split()[0] == "err_unknown_message":
                    print("disconnected: "+ "server received an unknown command")
                    sys.exit()
                elif msg.split()[0] == "forward_file":
                    self.forward_file(msg)
    def forward_message(self, parsed_message):
        str_received_msg = ""
        #extracting the message
        received_msg = parsed_message.split()
        received_msg = received_msg[2:]
        for i in received_msg: #concatenating the message
            str_received_msg += i + " "
        str_received_msg = str_received_msg[:-1]
        print(str_received_msg)

    def response_users_list(self, parsed_message):
        str_received_msg = ""
        #extracting the message
        received_msg = parsed_message.split()
        received_msg = received_msg[3:] 
        for i in received_msg:
            str_received_msg += i + " " #concatenating the message
        str_received_msg = str_received_msg[:-1]
        print("list: " + str_received_msg)

    def forward_file(self, parsed_message):
        p_msg = parsed_message.split()
        new_file_name = self.name + "_" + parsed_message.split()[4]
        #creating file with new name
        filee = open(new_file_name, "w")
        message = parsed_message.split()[5:]
        file_string = ""
        for i in range(len(message)): #concatenating the message
            file_string = file_string + message[i] + " "
        file_string = file_string[:-1]
        #copying the message
        filee.write(file_string)
        filee.close()
        print("file: " + p_msg[3] + ": " + p_msg[4])
        #raise NotImplementedError



# Do not change this part of code
if __name__ == "__main__":
    def helper():
        '''
        This function is just for the sake of our Client module completion
        '''
        print("Client")
        print("-u username | --user=username The username of Client")
        print("-p PORT | --port=PORT The server port, defaults to 15000")
        print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
        print("-w WINDOW_SIZE | --window=WINDOW_SIZE The window_size, defaults to 3")
        print("-h | --help Print this help")
    try:
        OPTS, ARGS = getopt.getopt(sys.argv[1:],
                                   "u:p:a:w", ["user=", "port=", "address=","window="])
    except getopt.error:
        helper()
        exit(1)

    PORT = 15000
    DEST = "localhost"
    USER_NAME = None
    WINDOW_SIZE = 3
    for o, a in OPTS:
        if o in ("-u", "--user="):
            USER_NAME = a
        elif o in ("-p", "--port="):
            PORT = int(a)
        elif o in ("-a", "--address="):
            DEST = a
        elif o in ("-w", "--window="):
            WINDOW_SIZE = a

    if USER_NAME is None:
        print("Missing Username.")
        helper()
        exit(1)

    S = Client(USER_NAME, DEST, PORT, WINDOW_SIZE)
    try:
        # Start receiving Messages
        T = Thread(target=S.receive_handler)
        T.daemon = True
        T.start()
        # Start Client
        S.start()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
