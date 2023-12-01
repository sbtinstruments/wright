# Setting up the development environment

First, you would need to replicate the production station. For replicating the station, you can follow the instructions described in: https://github.com/sbtinstruments/wharf.

Then, you are ready to set up the dev environment.

### SSH keys

In the current version of wharf (1/12/2023) we have added a feature that when you connect a USB driver to the Raspberry Pi, it will copy the `ssh/authorized_keys` file (if exists in the USB) to the `/home/root/.ssh` folder. It is important that you add your public key so you can develop using VScode remote extension.

### Set up VScode remote

Add the following configuration to your `~/.ssh/config`.

```
Host <hostname>
    HostName %h
    User root
    PasswordAuthentication no
    ForwardX11 yes
    ForwardAgent yes
```

Be aware that the `<hostname>` is set also using the udev service that reads the `identification.json` file from the USB drive you plug to the Raspberry Pi.

Second, you have to make the rootfs read and write by running the following command:

```sh
mount -o rw, remount /
```
> **Important**  
> Note that this is done only in the development station. The production station we keep it read only.


### Install extensions and set up display

After the previous step is finilized, we connect using the VScode Remote extension and we clone this repository in the Raspberry Pi:

```sh
git clone git@github.com:sbtinstruments/wright.git
```
If you want to forward the display, you will need to run a X11 server from your computer, e.g. VcXsrv on Windows.

Inside the `.vscode/` folder, we have created a debugging and extension file. Install all the recommended extensions and then reload the window and the terminal (just to make sure all the changes are applied). Make sure the `$DISPLAY` environmental variable is set by running:

```sh
echo $DISPLAY
```

Now you should be able to run in debugging mode pressing F5.

## Build your wharf-image in Yocto

Once you have commited the changes using the following inline config:

```sh
git -c "user.name=<your-name>" -c "user.email=<you-email>" commit -m "<your-commit-message>"
```
, you will like to create a production image. For that, you copy the commit hash to the file `wharfos.conf` in the repository https://github.com/sbtinstruments/sbt-yocto. 

Then, run the following commands in your Yocto dev container:

```sh
cli setup sbt-raspberry
cd build sbt-raspberry
bitbake wharf-image
```
Once finalized bitbaking, you need to write the image on a SD card. First, you download the image to your local computer:

```sh
docker cp <devcontainerID>:/sbt-yocto/build-sbt-raspberry/tmp/deploy/images/sbt-raspberry/wharf-image-sbt-raspberry-<date>.rootfs.wic </path/to/local/folder>
```
Using the Raspberry Pi imager (download here https://www.raspberrypi.com/software/), write the above `rootfs.wic` image in the SD card and when is done, plug it into the Raspberry Pi SD card holder. Connect the power supply and your new changes should be applied now.
