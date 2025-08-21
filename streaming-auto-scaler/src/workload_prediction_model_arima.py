import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

# Load data
df = pd.read_csv('../resources/nct.csv', header=None, names=['value'])

# Create a datetime index
df.index = pd.date_range(start='2020-01-01', periods=len(df), freq='T')  # Adjust start date as needed
ts = df['value']

# Visualize data
plt.figure(figsize=(10, 6))
plt.plot(ts)
plt.title('Time Series Data')
plt.xlabel('Time')
plt.ylabel('Value')
plt.show()

# Check stationarity
print("Check stationarity")
result = adfuller(ts)
print('ADF Statistic:', result[0])
print('p-value:', result[1])
for key, value in result[4].items():
    print('Critical Value (%s): %.3f' % (key, value))

# Differencing to achieve stationarity (if necessary)
ts_diff = ts.diff().dropna()

# Plot ACF and PACF
plot_acf(ts_diff)
plot_pacf(ts_diff)
plt.show()

# Fit ARIMA model
p = 1  # Replace with your determined value
d = 1  # Differencing order used earlier
q = 2  # Replace with your determined value
model = ARIMA(ts, order=(p, d, q))  # Replace p, d, q with appropriate values
model_fit = model.fit()
print(model_fit.summary())

# Forecasting
forecast = model_fit.forecast(steps=10)
forecast_conf_int = model_fit.get_forecast(steps=10).conf_int()

# Visualize forecast
plt.figure(figsize=(10, 6))
plt.plot(ts, label='Original')
plt.plot(forecast, label='Forecast', color='red')
plt.fill_between(forecast_conf_int.index,
                 forecast_conf_int.iloc[:, 0],
                 forecast_conf_int.iloc[:, 1], color='red', alpha=0.3)
plt.title('Time Series Forecast')
plt.legend()
plt.show()
