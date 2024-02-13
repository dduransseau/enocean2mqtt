
import time


from enocean.protocol.eep import EEP



start = time.time()
eep = EEP()

print(time.time() - start)

# start = time.time()
# eep.load_xml()

# print(time.time() - start)