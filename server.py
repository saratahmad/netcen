'''
This module defines the behaviour of server in your Chat Application
'''
import sys
import getopt
import socket
import util
from queue import Queue
import random
from threading import Thread
import time


class Server:
    '''
    This is the main Server Class. You will to write Server code inside this class.
    '''
    def __init__(self, dest, port, window):
        self.server_addr = dest
        self.server_port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(None)
        self.sock.bind((self.server_addr, self.server_port))
        self.window = window
        self.user_info = []
        self.user_names = []
        self.user_dictionary = {}
        self._dictionary = {}
    def start(self):
        '''
        Main loop.
        continue receiving messages from Clients and processing it
        '''
        while True:
            #print("Server is listening")
            message, address = self.sock.recvfrom(4096) #message recieved
            address_port = address[1]
            decoded_message = message.decode("utf-8")
            parsed_message = util.parse_packet(decoded_message)
            client_qUeue = Queue(maxsize=0)
            #finding client in dictionary
            if address_port not in self._dictionary:
                self._dictionary[address_port] = client_qUeue
            if parsed_message[0] == "start":
                #sending start packets
                init_seq_num = int(parsed_message[1]) + 1  
                init_packet1 = util.make_packet("ack", init_seq_num,)
                self.sock.sendto(init_packet1.encode("utf-8"), ("localhost", address_port))

            if parsed_message[0] == "data":
                #recieving data from the client and sending acks
                validate_check_sum = util.validate_checksum(decoded_message)
                if validate_check_sum: #validating checksums 
                    self._dictionary[address_port].put(parsed_message[2])
                    init_seq_num = int(parsed_message[1]) + 1
                    init_packet1 = util.make_packet("ack", init_seq_num,)
                    self.sock.sendto(init_packet1.encode("utf-8"), ("localhost", address_port))

            if parsed_message[0] == "ack":
                #putting acks in the queue assigned to each address   
                self._dictionary[address_port].put(parsed_message[0])
                self._dictionary[address_port].put(parsed_message[1])
            if parsed_message[0] == "end":
                #accepting the end packet and sending the acks
                init_seq_num = int(parsed_message[1]) + 1
                init_packet1 = util.make_packet("ack", init_seq_num,)
                bool_check = 0
                if bool_check == 0:
                	self.sock.sendto(init_packet1.encode("utf-8"), ("localhost", address_port))
                #starting a new thread if a new client joins
                thread_new_cleint = Thread(target=self.receive_handler, args=(address_port,))
                thread_new_cleint.daemon = True
                thread_new_cleint.start()

    def receive_handler(self, address_port):
        msg = ""
        while not self._dictionary[address_port].empty():
            msg = msg + self._dictionary[address_port].get()
        # print("im here ", msg)
        if msg.split()[0] == "join":
            #join function
            self.join(address_port, msg)
        elif msg.split()[0] == "send_message":
            #sendin message
            self.send_message(address_port, msg)
        elif msg.split()[0] == "disconnect":
            #disconnecting the client
            self.disconnect(address_port)
        elif msg.split()[0] == "request_users_list":
            #list
            self.request_users_list(address_port, msg)
        elif msg.split()[0] == "send_file":
            #sending file
            self.send_file(address_port, msg)                
        else:
            index = self.user_info.index(address_port)-1
            sender_name = self.user_info[index]
            new_message = util.make_message("err_unknown_message", 2)
            self.start_packet(self.user_dictionary[sender_name])
            #checking the ack recieved
            if self._dictionary[address_port].get() == "ack":
                self.sending_chunks(new_message, self.user_dictionary[sender_name])
            print("disconnected: "+ sender_name + " sent unknown command")

    def window_trans(self, window_s, seq_num, final_list, address_port):
        for i in range(0, window_s):
            #making packets and sending 3 packets in a window
            mess = util.make_packet("data", seq_num+i, final_list[i])
            self.sock.sendto(mess.encode("utf-8"), ("localhost", address_port))
            pack_trac = i
            #returning the index
        return pack_trac +1
    
    def sending_chunks(self, initial_msg, address_port):
        retry = 0
        yes = True
        #making chunks
        final_list = self.make_chunks(initial_msg)
        seq_num = int(self._dictionary[address_port].get()) #sequence number
        len_lis = len(final_list) #length list

        if (len_lis < util.WINDOW_SIZE): #determining size of window to traverse the chunks list
            win_siz = len_lis
        elif len_lis > util.WINDOW_SIZE:
            win_siz = util.WINDOW_SIZE
        pack_trac = self.window_trans(win_siz, seq_num, final_list, address_port) #calling the transmission
        while(pack_trac < len_lis):
            try: 
                if self._dictionary[address_port].get(block = True, timeout= util.TIME_OUT) == "ack":
                    #comparing the acks received with the expected sequence numnber
                    if int(self._dictionary[address_port].get()) == (int(seq_num) + 1):
                        #sliding the window acks sending the next 
                        message = util.make_packet("data", int(seq_num + pack_trac), final_list[pack_trac])
                        self.sock.sendto(message.encode("utf-8"), ("localhost", address_port))
                        pack_trac = pack_trac + 1
                seq_num = seq_num + 1
            except:
                #sending packets for retransmission                                        
                if (retry <= util.NUM_OF_RETRANSMISSIONS):
                    if yes == True:
                        self.window_trans(win_siz, seq_num, final_list, address_port)
                        retry = retry + 1
                    else:
                        break
                else:
                    seq_num = seq_num + 1
        # sends the end packet, ending the connection
        self._dictionary[address_port].get()
        vall = int(self._dictionary[address_port].get())
        #making packet
        end_packet = util.make_packet("end", vall,)
        self.sock.sendto(end_packet.encode("utf-8"), ("localhost", address_port))
        # gets from the queue to remove the ack and sequence number of end packet
        self._dictionary[address_port].get()
        self._dictionary[address_port].get()

    def make_chunks(self, initial_packet):
        n = util.CHUNK_SIZE
        #making chunks of size 1400
        chunks = [initial_packet[i:i+n] for i in range(0, len(initial_packet), n)]
        return chunks

    def start_packet(self, address_port):
        seq_no = random.randint(0, 1000)
        init_packet1 = util.make_packet("start", seq_no,)
        self.sock.sendto(init_packet1.encode("utf-8"), ("localhost", address_port))
    def join(self, address_port, parsed_message):
        new_user = parsed_message.split()[2] #name
        check = 0
        for names in self.user_dictionary:
            if names == new_user:
                check = 1
        #for the case where there is no user
        hmm = self.user_dictionary
        if len(hmm) == 0:
            new_user = parsed_message.split()[2] #name
            self.user_dictionary[new_user] = address_port
            self.user_info.append(new_user)
            self.user_info.append(address_port)
            self.user_names.append(new_user)
            print(f"join: {new_user}")
        #for the case where client limit reached
        elif len(self.user_dictionary) >= util.MAX_NUM_CLIENTS:
            print("disconnected: server full")
            new_message = util.make_message("err_server_full", 2)
            self.start_packet(address_port)
            bool_check = True
            if boo_check == True:
                if self._dictionary[address_port].get() == "ack":
                	self.sending_chunks(new_message, address_port)
        elif check == 1:
            #case where username unavailable
            for names in self.user_dictionary:
                if names == new_user:
                    print("disconnected: username not available")
                    new_message = util.make_message("err_username_unavailable", 2)
                    self.start_packet(address_port)
                    if self._dictionary[address_port].get() == "ack":
                        self.sending_chunks(new_message, address_port)
        else:
            #case where client joins
            new_user = parsed_message.split()[2] #name
            self.user_dictionary[new_user] = address_port
            self.user_info.append(new_user)
            self.user_info.append(address_port)
            self.user_names.append(new_user)
            print(f"join: {new_user}")

    def disconnect(self, address_port):
        index = self.user_info.index(address_port)-1
        sender_name = self.user_info[index]
        for names in self.user_names:
            if names == sender_name:
                #deleting from dictionary
                del self.user_dictionary[sender_name]
        print("disconnected: "+sender_name)    
    def send_message(self, address_port, parsed_message):
        index = self.user_info.index(address_port)-1
        sender_name = self.user_info[index]
        data_list = parsed_message.split()
        no_of_clients = int(data_list[2]) #number of clients
        final_index = 0
        to_send_list = [] #packets being forwarded to them
        for i in  range(3, (3+no_of_clients)):
            to_send_list.append(data_list[i])
            final_index = i
        #removing duplicates
        to_send_list = list(dict.fromkeys(to_send_list))
        print_duplicates = 'a'
        for a_i in to_send_list:
            check = 0
            for j in self.user_names:
                if a_i == j:
                    check = 1
                    msg_string = "msg: " + sender_name + ": "
                    message_by_sender = data_list[final_index+1:]
                    for i in message_by_sender:
                        msg_string = msg_string + i + " "
                    msg_string = msg_string[:-1]
                    new_message = util.make_message("forward_message", 4, msg_string)
                    self.start_packet(self.user_dictionary[a_i])
                    #checking in the dictionary and sending acks
                    if self._dictionary[self.user_dictionary[a_i]].get() == "ack":
                        self.sending_chunks(new_message, self.user_dictionary[a_i])
                    #to avoid printing multiple times
                    while print_duplicates == 'a':
                        print(f"msg: {sender_name}")
                        print_duplicates = 'b'
                    break
            if check == 0:
                #user unavailable
                print("msg: " + sender_name)
                print("msg: " + sender_name + " to non-existent user " + a_i)
    def request_users_list(self, address_port, parsed_message):
        index = self.user_info.index(address_port)-1
        sender_name = self.user_info[index]
        #getting length and names in dictionary
        string_of_names = ""
        l_dict = len(self.user_dictionary)
        length_dictionary = str(l_dict)
        usernames = list(self.user_dictionary.keys())
        #sorting the names
        sorted_list = sorted(usernames)
        for names in sorted_list:
            string_of_names = string_of_names + names + " "
        string_of_names = string_of_names[:-1]
#sending packets
        print("request_users_list: " + sender_name)
        new_message = util.make_message("response_users_list", 3, length_dictionary + " " + string_of_names)
        self.start_packet(self.user_dictionary[sender_name])
        if self._dictionary[self.user_dictionary[sender_name]].get() == "ack":
            self.sending_chunks(new_message, self.user_dictionary[sender_name])

    def send_file(self, address_port, parsed_message):
        index = self.user_info.index(address_port)-1
        sender_name = self.user_info[index]

        data_list = parsed_message.split()
        no_of_clients = int(data_list[2]) #number of clients
        last_index = 0
        to_send_list = [] #packets being forwarded to them
        for i in  range(3, (3+no_of_clients)):
            to_send_list.append(data_list[i])
            last_index = i
#message to be sent
        file_data = data_list[last_index+2:]
        file_name = data_list[last_index+1]
        #removing duplicates
        to_send_list = list(dict.fromkeys(to_send_list))
        file_string = ""
        for words in file_data:
            file_string = file_string + words + " "
        file_string = file_string[:-1]
        print_duplicates = 'a'
        for a in to_send_list:
            check = 0
            for j in self.user_names:
                if a == j:
                    check = 1

                    data = "1 " + sender_name + " " + file_name + " " + file_string
                    new_message = util.make_message("forward_file", 4, data)
                    self.start_packet(self.user_dictionary[a])
                    #chekcing ack from the given queue and sending chunks
                    if self._dictionary[self.user_dictionary[a]].get() == "ack":
                        self.sending_chunks(new_message, self.user_dictionary[a])
                    #to avoid duplicate printing of name
                    while print_duplicates == 'a':
                        print(f"file: {sender_name}")
                        print_duplicates = 'b'
                    break
            if check == 0:
                print("file: " + sender_name + " to non-existent user " + a)



# Do not change this part of code

if __name__ == "__main__":
    def helper():
        '''
        This function is just for the sake of our module completion
        '''
        print("Server")
        print("-p PORT | --port=PORT The server port, defaults to 15000")
        print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
        print("-w WINDOW | --window=WINDOW The window size, default is 3")
        print("-h | --help Print this help")

    try:
        OPTS, ARGS = getopt.getopt(sys.argv[1:],
                                   "p:a:w", ["port=", "address=","window="])
    except getopt.GetoptError:
        helper()
        exit()

    PORT = 15000
    DEST = "localhost"
    WINDOW = 3

    for o, a in OPTS:
        if o in ("-p", "--port="):
            PORT = int(a)
        elif o in ("-a", "--address="):
            DEST = a
        elif o in ("-w", "--window="):
            WINDOW = a

    SERVER = Server(DEST, PORT,WINDOW)
    try:
        SERVER.start()
    except (KeyboardInterrupt, SystemExit):
        exit()
