#! /usr/bin/python3

import concurrent.futures
import platform
import pprint
import subprocess


def get_model_info():
    model_info = dict()

    with open("/sys/class/dmi/id/product_name", "r") as prod_name:
        model_info.update(model=prod_name.readline().splitlines()[0].strip())

    with open("/sys/class/dmi/id/product_serial", "r") as prod_serial:
        model_info.update(serial=prod_serial.readline().splitlines()[0].strip())

    return model_info


def get_cpu_info():
    cpu_info = list()

    results = (
        subprocess.run(
            ["lscpu"],
            capture_output=True,
            text=True,
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
    results = (
        subprocess.run(["lsmem"], capture_output=True, text=True)
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
    serial = None

    results = subprocess.run(
        ["smartctl", "-i", f"/dev/{disk}"],
        capture_output=True,
        text=True,
    ).stdout.split("\n")

    for line in results:
        if line.startswith("Serial"):
            serial = line.split(":")[1].strip()

    return disk, serial


def get_disk_info():
    disk_info = list()
    disk_list = list()

    lsblk_list = (
        subprocess.run(
            [
                "lsblk",
                "--noheadings",
                "--list",
                "--nodeps",
                "--output",
                "KNAME,HCTL,ROTA,SIZE",
            ],
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .split("\n")
    )

    for item in lsblk_list:
        disk_spec = item.split()

        disk = dict()

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


def main():
    host_info = dict()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        cpus_future = executor.submit(get_cpu_info)
        mem_future = executor.submit(get_mem_info)
        model_future = executor.submit(get_model_info)
        disks_future = executor.submit(get_disk_info)

    host_info["host"] = platform.node()
    host_info["disks"] = (disks_future.result())
    host_info["cpus"] = cpus_future.result()
    host_info.update(mem_future.result())
    host_info.update(model_future.result())

    pprint.pprint(host_info)

    return 0


if __name__ == "__main__":
    main()
