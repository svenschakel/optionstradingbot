Introduction
============

This repository includes Python scripts automating various options income trading strategies. The bot connects to the Interactive Brokers API and runs with minimal manual intervention. Currently, it contains two basic trading strategies: the short strangle and iron condor.

Installation
============
Everything has been optimized to allow for a quick and easy installation process. By following the steps below, installation should only take a few minutes. If you've already automated other trading strategies in IB, many of these steps can be ignored.

1. Install the latest version of python on https://www.python.org/downloads/. Make sure to select 'Add to path' during the installation of Python.
2. With Python installed, we can install the required packages by typing the following commands in cmd (make sure to insert the path to where you saved the repository): 

::


  cd /path/to/directory
  pip install -r requirements.txt

3. Subsequently, install TWS or IB Gateway and the TWS API. In case you want to use IBC(https://github.com/IbcAlpha/IBC) to automate logging in, you'll need the offline version of TWS which can be downloaded at https://www.ibtws.com/en/trading/tws-offline-stable.php. Download the TWS API at https://interactivebrokers.github.io/.
4. To be able to receive market data from IB, you need to deposit a minimum amount of $500. Furthermore, two market data subscriptions are required to be able to receive market data from IB, namely: "US Securities Snapshot and Futures Value Bundle" and "US Equity and Options Add-On Streaming Bundle".
5. Next, in TWS or Gateway, go to "Global Configuration" --> "API" --> "Settings". Here you need to select "Enable ActiveX and Socket Clients and deselect "Read-Only API".
6. In the repository folder, run the setup file. 
7. In the config.ini file you can now configure everything to your liking. 
8. Finally, the only thing left to do is to make Windows run the bot at certain times. This can be done with 'Task Scheduler' from Windows itself and the .bat files contained in the repository.

