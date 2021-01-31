# script for concurrent downloading large amount of files
import csv
import os
import asyncio
import aiofiles
import aiohttp


generated_ids = set(f[:-4] for f in os.listdir("recommendations"))

with open('all.csv', newline='') as csvfile:
    reader = csv.reader(csvfile)
    file_ids = set(i[0] for i in reader)

student_ids = file_ids - generated_ids

MAX_TASKS = 5
# MAX_TIME = 10
SUPERPARENT_TOKEN = "LPvcnOwwBFchVZFvn0Vg0NPIezfoo45C5k-YZtyXmqwEvYYtm1StNWJeL5i0uXq9sMDQrAo2ymo2AEr1TAZTrA"


async def download(ids):
    tasks = []
    sem = asyncio.Semaphore(MAX_TASKS)
    counter = 0

    async with aiohttp.ClientSession(cookies={'session': SUPERPARENT_TOKEN}) as session:
        for student_id in ids:
            tasks.append(
                # Wait max seconds for each download
                asyncio.wait_for(
                    download_one(
                        f"https://app.ru/recommendations/pdf/{student_id}",
                        session,
                        sem,
                        f"recommendations/{student_id}.pdf",
                        counter=counter),
                    # timeout=MAX_TIME,
                )
            )
            counter += 1

        return await asyncio.gather(*tasks)


async def download_one(url, session, sem, dest_file, counter=None):
    if counter % 100 == 0:
        print(f"Processing {counter+1} task")

    async with sem:
        print(f"Go {url}")
        async with session.get(url) as res:
            content = await res.read()

        # Check everything went well
        if res.status != 200:
            print(f"Download failed: {res.status}. {url}")
            return
        print("Download OK")

        async with aiofiles.open(dest_file, "+wb") as f:
            await f.write(content)
            # No need to use close(f) when using with statement


if __name__ == "__main__":
    asyncio.run(download(student_ids))
    print("Done!")
