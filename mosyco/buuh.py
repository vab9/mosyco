# import numpy as np
# import matplotlib.pyplot as plt

# import logging
# log = logging.getLogger(__name__)

# plt.axis([0, 10, 0, 1])
# plt.ion()

# for i in range(20):
#     y = np.random.random()
#     log.warn('hey')
#     plt.scatter(i, y)
#     plt.pause(0.05)

# while True:
#     plt.pause(0.05)

# import asyncio
# import random

# q = asyncio.Queue()


# async def producer(num):
#     while True:
#         await q.put(num + random.random())
#         await asyncio.sleep(random.random())

# async def consumer(num):
#     while True:
#         value = await q.get()
#         print('Consumed', num, value)

# loop = asyncio.get_event_loop()

# for i in range(6):
#     loop.create_task(producer(i))

# for i in range(3):
#     loop.create_task(consumer(i))

# loop.run_forever()
