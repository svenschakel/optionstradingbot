# Introduction

This repository contains Python scripts designed to automate various options income trading strategies in Interactive Brokers. Currently, it supports two foundational strategies: the **short strangle** and **iron condor**.

---

# Installation

1. **Install Python**  
   Download and install the latest version of Python from [python.org](https://www.python.org/downloads/). During installation, ensure you select the **‘Add to PATH’** option.

2. **Install Required Packages**  
   Open a command prompt (cmd) and navigate to the directory where the repository is saved. Then, run the following commands to install the necessary dependencies:

   ```bash
   cd /path/to/directory
   pip install -r requirements.txt
   ```

3. **Set Up TWS or IB Gateway**  
   - Download and install **TWS** (Trader Workstation) or **IB Gateway**.  
   - If you wish to automate login using ([IBC](https://github.com/IbcAlpha/IBC)), download the **offline version** of TWS from [this link](https://www.ibtws.com/en/trading/tws-offline-stable.php).  
   - Additionally, download the TWS API from [Interactive Brokers API](https://interactivebrokers.github.io/).

4. **Market Data Subscriptions**  
   - Ensure your IB account has a minimum deposit of $500 to access market data.  
   - Subscribe to the following market data bundles:  
     - **US Securities Snapshot and Futures Value Bundle**  
     - **US Equity and Options Add-On Streaming Bundle**

5. **Configure API Settings**  
   - In TWS or IB Gateway, navigate to **Global Configuration** → **API** → **Settings**.  
   - Enable **‘ActiveX and Socket Clients’** and disable **‘Read-Only API’**.

6. **Run Setup Script**  
   - Navigate to the repository folder and execute the setup script.

7. **Edit Configuration**  
   - Open the `config.ini` file and customize it according to your preferences.

8. **Automate the Bot with Task Scheduler**  
   - Use Windows Task Scheduler to schedule the execution of the .bat file corresponding to your desired strategy. These .bat files will, in turn, execute the associated Python script for the selected strategy.
