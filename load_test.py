#Referenced from https://jackskylord.medium.com/python-aiohttp-and-asyncio-a0e55b18f77a

import aiohttp
import asyncio
import numpy as np
from PIL import Image
import io
import time


async def generate_random_image(width, height):
    array = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    image = Image.fromarray(array, 'RGB')
    return image


# async def send_image(session, image, url):
#     buffer = io.BytesIO()
#     image.save(buffer, format="PNG")
#     buffer.seek(0)
#     data = aiohttp.FormData()
#     data.add_field('image', buffer, filename='image.png', content_type='image/png')
#     async with session.post(url, data=data) as response:
#         start_time = time.time()
#         resp = await response.read()
#         return response.status, time.time() - start_time

async def send_image(session, image, url):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    data = aiohttp.FormData()
    data.add_field('image', buffer, filename=f'image-{int(time.time())}.png', content_type='image/png')

    start_time = time.time()
    async with session.post(url, data=data) as response:
        await response.read()
        response_time = time.time() - start_time
    return response.status, response_time


async def load_test_continuous(url, initial_rate, increase, duration):
    rate = initial_rate
    async with aiohttp.ClientSession() as session:
        while True:
            print(f"Testing at {rate} requests per second...")
            start_time = time.time()
            total_requests = rate * duration
            tasks = []
            for _ in range(total_requests):
                image = await generate_random_image(640, 480)
                task = send_image(session, image, url)
                tasks.append(task)
                await asyncio.sleep(1 / rate)  # Delay to match the target rate

            responses = await asyncio.gather(*tasks)
            response_times = []
            for status, resp_time in responses:
                if status != 200:
                    print(f"Unexpected status code {status} with response time {resp_time}")
                response_times.append(resp_time)
            average_time = sum(response_times) / len(response_times)
            end_time = time.time()
            total_test_diff = end_time - start_time
            print(f"Average response time for {rate} requests per second is {average_time}")
            print(f"For a total throughput of {total_requests / total_test_diff} inferences per second")
            rate += increase

if __name__ == '__main__':
    #url = 'http://localhost:5000/upload'
    url = 'https://squid-app-bwmg4.ondigitalocean.app/upload'
    initial_rate = 1
    increment = 1
    time_per_test = 10

    asyncio.run(load_test_continuous(url, initial_rate, increment, time_per_test))