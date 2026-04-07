# IEEETestCases Documentation

## Project Overview
This project is a simulation dashboard for OpenDSS, designed to analyze and visualize power distribution systems. It provides an interactive web interface for users to input parameters, run simulations, and view results.

## File Structure
- `Simulacion_DASH_VFinal.py`: Contains the main application logic for the OpenDSS simulation dashboard. It initializes the OpenDSS engine, defines functions to calculate losses, and sets up a Dash web application with various interactive components and callbacks.
  
- `welcome.py`: Implements the welcome page, featuring a menu with a start button that navigates to the main simulation page.

- `app.py`: Serves as the entry point for the Dash application, importing the welcome page and the main simulation page, and setting up the routing between them.

## Setup Instructions
1. **Install Required Packages**: Ensure you have the necessary Python packages installed. You can do this using pip:
   ```
   pip install dash plotly pandas
   ```

2. **OpenDSS Installation**: Make sure you have OpenDSS installed and properly configured on your system.

3. **Run the Application**: Execute the `app.py` file to start the Dash application:
   ```
   python app.py
   ```

4. **Access the Dashboard**: Open your web browser and navigate to `http://127.0.0.1:8050` to access the dashboard.

## Usage
- Start on the welcome page, where you can click the start button to navigate to the simulation dashboard.
- Input the necessary parameters for your simulation and view the results interactively.

## Contributing
Contributions to improve the functionality and usability of the dashboard are welcome. Please submit a pull request or open an issue for discussion.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.