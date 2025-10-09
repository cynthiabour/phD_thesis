"""
sniffer from two com port
"""


import serial

baud_rate = 19200  # whatever baudrate you are listening to
com_port1 = 'COM6'  # replace with your first com port path
com_port2 = 'COM6'  # replace with your second com port path

pc = serial.Serial(com_port1, baud_rate)
r2 = serial.Serial(com_port2, baud_rate)

while True:
    # Replace \n with the expected EOL
    command = pc.read_until(expected="\n".encode())
    print(f"--> {command.decode()}")
    r2.write(command)
    reply = r2.readline()
    print(f"<-- {reply.decode()}")
    pc.write(reply)