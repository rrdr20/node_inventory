"""Collects node inventory and posts to Redis."""

import concurrent.futures
import logging
import platform
import subprocess
import time

import redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_log = logging.StreamHandler()
console_log.setLevel(logging.INFO)

formatter = logging.Formatter("%(levelname)s: %(message)s")

console_log.setFormatter(formatter)
logger.addHandler(console_log)


def get_model_info():
    """Collects the node model and serial number from system files and returns
    the map.
    """
    model_info = {}

    with open("/sys/class/dmi/id/product_name", "r", encoding="utf-8") as prod_name:
        model_info.update(model=prod_name.readline().splitlines()[0].strip())

    with open("/sys/class/dmi/id/product_serial", "r", encoding="utf-8") as prod_serial:
        model_info.update(serial=prod_serial.readline().splitlines()[0].strip())

    return model_info


def get_cpu_info():
    """Reads the output of lscpu and parses thread, core, socket and model info
    and returns the map.
    """
    cpu_info = []

    results = (
        subprocess.run(
            ["lscpu"],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .split("\n")
    )

    for line in results:
        if line.startswith("Thread"):
            threads = line.split(":")[1].strip()
        elif line.startswith("Core"):
            cores = line.split(":")[1].strip()
        elif line.startswith("Socket"):
            sockets = line.split(":")[1].strip()
        elif line.startswith("Model name"):
            model = line.split(":")[1].strip()

    for i in range(0, int(sockets)):
        cpu_info.append(
            {
                "cpu_num": f"{i}",
                "model": model,
                "cores": cores,
                "threads": threads,
            }
        )

    return cpu_info


def get_mem_info():
    """Parses online memory from the lsmem command and returns the map."""
    results = (
        subprocess.run(["lsmem"], capture_output=True, text=True, check=True)
        .stdout.strip()
        .split("\n")
    )

    for line in results:
        if line.startswith("Total online"):
            mem = line.split(":")[1].strip()

    mem_info = {
        "memory": mem,
    }

    return mem_info


def get_disk_serial(disk):
    """Runs smartctl with the disk specified, parses the serial number of the
    disk and returns a tuple of the disk and the serial number.
    """
    serial = None

    results = subprocess.run(
        ["smartctl", "-i", f"/dev/{disk}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")

    for line in results:
        if line.startswith("Serial"):
            serial = line.split(":")[1].strip()

    return disk, serial


def get_disk_info():
    """Collects the disk information from the host using the lsblk and smartctl
    commands and returns a map.
    """
    disk_info = []
    disk_list = []

    lsblk_list = (
        subprocess.run(
            [
                "lsblk",
                "--noheadings",
                "--list",
                "--nodeps",
                "--exclude",
                "7,11",
                "--output",
                "KNAME,HCTL,ROTA,SIZE",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .split("\n")
    )

    for item in lsblk_list:
        disk_spec = item.split()

        disk = {}

        disk_list.append(disk_spec[0])

        if disk_spec[0].startswith("nvme"):
            disk["name"] = disk_spec[0]
            disk["size"] = disk_spec[2]
            disk["type"] = "nvme"
        else:
            disk["name"] = disk_spec[0]
            disk["path"] = disk_spec[1]
            disk["size"] = disk_spec[3]
            disk["type"] = "nvme"
            if disk_spec[2] == "1":
                disk["type"] = "hdd"
            else:
                disk["type"] = "ssd"

        disk_info.append(disk)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        disk_serials = executor.map(get_disk_serial, disk_list)

    for serial in disk_serials:
        for disk in disk_info:
            if serial[0] == disk["name"]:
                disk["serial"] = serial[1]

    return disk_info


def get_disk_temps(disk: dict):
    """Runs the smartctl command on the disk and parses the temperature from
    the output. Returns a formatted string.
    """
    temp = None

    results = subprocess.run(
        ["smartctl", "-A", f"/dev/{disk['name']}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")

    if disk["name"].startswith("nvme"):
        for line in results:
            if line.startswith("Temperature:"):
                temp = line.split()[1].strip()
    else:
        for line in results:
            if line.startswith("194 Temperature"):
                temp = line.split()[9].strip()

    return f"{disk['name']} {temp}"


def main():
    """Connects to the Redis server and sets info based on the information
    collected from the node.
    """
    try:
        host_info = {}
        host_info["host"] = platform.node()

        logger.info("Connecting to Redis server...")
        redis_conn = redis.Redis(host="192.168.10.6", port=6379, db=0)
        redis_conn.setnx(f"{host_info['host']}", "connected")
        logger.info("Connected to Redis server.")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            cpus_future = executor.submit(get_cpu_info)
            mem_future = executor.submit(get_mem_info)
            model_future = executor.submit(get_model_info)
            disks_future = executor.submit(get_disk_info)

        logger.info("Gathering disk info.")
        host_info["disks"] = disks_future.result()

        logger.info("Gathering CPU info.")
        host_info["cpus"] = cpus_future.result()

        logger.info("Gathering memory info.")
        host_info.update(mem_future.result())

        logger.info("Gathering platform info.")
        host_info.update(model_future.result())

        logger.info(host_info)

        while True:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                temp_futures = executor.map(get_disk_temps, host_info["disks"])
                temp_list = list(temp_futures)
                print("|".join(temp_list))
                time.sleep(5)

    except Exception as err:
        logger.error(err)

    return 0


if __name__ == "__main__":
    main()
