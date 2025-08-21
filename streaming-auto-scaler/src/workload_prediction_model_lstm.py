import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from keras.models import Sequential
from keras.layers import Dense, LSTM
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error
import tensorflow as tf

# Original time-series to predict.
data_path = "../resources/nct.csv"
# Model URI to save and load the trained model.
model_uri = '../resources/nct_lstm_model.keras'
# Predictions output file.
predictions_output = '../resources/predictions_open_closed.csv'
# Fraction of the dataset to use for training.
training_dataset_fraction = 0.125


def organize_data(sequence_data, history_length=1):
    """
    Organize the data into the format required for LSTM training.
    """
    input_data, target_data = [], []
    # Create sliding windows of `history_length` as input and the next value as target
    for idx in range(len(sequence_data)-history_length-1):
        fragment = sequence_data[idx:(idx+history_length), 0]
        input_data.append(fragment)
        target_data.append(sequence_data[idx + history_length, 0])
    return np.array(input_data), np.array(target_data)


def load_data(data_path):
    """
    Load the dataset from the specified path.
    """
    return pd.read_csv(data_path, usecols=[0], engine='python')


def flatten_list(lst):
    """
    Flatten a list of lists.
    """
    return [item for sublist in lst for item in (flatten_list(sublist) if isinstance(sublist, list) else [sublist])]


def plot_dataframe(dataframe, label):
    """
    Plot the original dataset for inspection purposes.
    """
    print("Plotting original data...")
    plt.figure(figsize=(8, 4))
    plt.plot(dataframe, label=label)
    plt.legend()
    plt.show()


def build_model_from_trace():
    """
    Build an LSTM model to predict the next value in a time-series dataset.
    """
    history_length = 1
    epochs = 100
    batch_size = 1

    dataframe = load_data(data_path)
    # Plot the original dataset
    plot_dataframe(dataframe, 'Original Data')

    # Convert to Numpy Array and Normalize
    print("Converting to Numpy Array and Normalizing...")
    array = dataframe.values.astype('float32')
    scaler_toolbox = MinMaxScaler(feature_range=(0, 1))
    normalized_data = scaler_toolbox.fit_transform(array)

    # Divide into Training and Test Segments
    print("Dividing into Training and Test Segments...")
    partition_size = int(len(normalized_data) * training_dataset_fraction)
    remainder_size = len(normalized_data) - partition_size
    train_partition, test_partition = (normalized_data[0:partition_size,:],
                                       normalized_data[partition_size:len(normalized_data),:])
    # Organize training and test data into input/target pairs
    train_input, train_target = organize_data(train_partition, history_length)
    test_input, test_target = organize_data(test_partition, history_length)
    # Reshape into [samples, timesteps, features] for LSTM
    train_input = np.reshape(train_input, (train_input.shape[0], 1, train_input.shape[1]))
    test_input = np.reshape(test_input, (test_input.shape[0], 1, test_input.shape[1]))

    # Build and Train LSTM Network
    print("Building and Training LSTM Network...")
    model = Sequential()
    model.add(LSTM(4, input_shape=(1, history_length)))
    model.add(Dense(1))
    model.compile(loss='mean_squared_error', optimizer='adam')
    model.fit(train_input, train_target, epochs=epochs, batch_size=batch_size, verbose=2)

    # Make Predictions and Assess Model
    print("Making Predictions and Assessing Model...")
    train_forecast = model.predict(train_input)
    test_forecast = model.predict(test_input)

    # Inverse transform predictions and targets
    train_forecast = scaler_toolbox.inverse_transform(train_forecast)
    train_target = scaler_toolbox.inverse_transform([train_target])
    test_forecast = scaler_toolbox.inverse_transform(test_forecast)
    test_target = scaler_toolbox.inverse_transform([test_target])

    # Compute RMSE
    train_evaluation = np.sqrt(mean_squared_error(train_target[0], train_forecast[:,0]))
    print('Training Evaluation: %.2f RMSE' % (train_evaluation))
    test_evaluation = np.sqrt(mean_squared_error(test_target[0], test_forecast[:,0]))
    print('Testing Evaluation: %.2f RMSE' % (test_evaluation))

    # Save model
    print("Saving Model...")
    model.save(model_uri)

    # Visualizing Original Data and Forecasts
    plt.figure(figsize=(8, 4))
    plt.plot(scaler_toolbox.inverse_transform(normalized_data), label='Original Data')
    plt.plot([item for item in train_forecast], label='Training Forecast')
    plt.plot([item+len(train_forecast) for item in range(len(test_forecast))], test_forecast, label='Testing Forecast')
    plt.legend()
    plt.show()


def predict_next_values_and_compare(model_uri, input_sequence, actual_values, n_steps, closed_loop=False):
    """
    Predict the next values in a time-series dataset using an LSTM model and compare the predictions to the actual values.
    You can choose whether to use the predicted values in the next timestep (closed loop) or the actual values (open loop).
    The generated sequences will be of a size equal to the input sequence. This function assumes that the model has been
    previously stored in the specified URI (if not, please run the build_model_from_trace() function first).
    """
    model = tf.keras.models.load_model(model_uri)
    current_sequence = input_sequence.copy()
    prediction_batch_size = len(input_sequence)
    predictions = []
    prediction_errors = []
    i = 0

    while i < n_steps:
        # Reshape the current sequence to match the model's input shape
        input_data = np.reshape(current_sequence, (len(current_sequence), 1, 1))

        # Use the LSTM model to predict the next timestep
        next_prediction = model.predict(input_data)

        # Store the prediction
        predictions.append(next_prediction.tolist())
        i += prediction_batch_size

        # Update the current sequence depending on closed/open loop
        if closed_loop:
            current_sequence = next_prediction  # feed prediction back as input
        else:
            current_sequence = actual_values[i:i + prediction_batch_size]  # feed actual next values

    return predictions, prediction_errors


if __name__ == "__main__":
    # build_model_from_trace()
    data_path = "../resources/nct.csv"
    model_uri = '../resources/nct_lstm_model.keras'

    # Load and normalize data
    dataframe = load_data(data_path)
    array = dataframe.values.astype('float32')
    scaler_toolbox = MinMaxScaler(feature_range=(0, 1))
    normalized_data = scaler_toolbox.fit_transform(array)

    # Split dataset for input and actual values
    partition_size = int(len(normalized_data) * 0.125) + 1
    input_sequence = normalized_data[0:partition_size,:]
    actual_values = normalized_data[partition_size:,:]

    # Predict future values
    elements_to_predict = 80640 - 10080
    predictions, errors = predict_next_values_and_compare(model_uri, input_sequence, actual_values, elements_to_predict, True)

    # Flatten predictions and actual values for evaluation
    predictions_flatten = flatten_list(predictions)
    actual_values_flatten = flatten_list(actual_values)
    min_comparable_len = min(len(predictions_flatten), len(actual_values_flatten))

    # Evaluate predictions (normalized)
    evaluation = np.sqrt(mean_squared_error(predictions_flatten[0:min_comparable_len],
                                            actual_values_flatten[0:min_comparable_len]))
    print('Prediction Evaluation (normalized): %.2f RMSE' % evaluation)

    # Evaluate predictions (denormalized)
    evaluation = np.sqrt(mean_squared_error(scaler_toolbox.inverse_transform(actual_values)[0:min_comparable_len],
                                            scaler_toolbox.inverse_transform(
                                                np.reshape(predictions_flatten, (len(predictions_flatten), 1))
                                            )[0:min_comparable_len]))
    print('Prediction Evaluation (denormalized): %.2f RMSE' % evaluation)

    # Save the predictions to a file for plotting purposes
    denormalized_predictions = scaler_toolbox.inverse_transform(np.reshape(predictions_flatten, (len(predictions_flatten), 1)))
    np.savetxt(predictions_output, denormalized_predictions, delimiter=',', fmt='%d')

    # Plot the comparison between predicted and actual values
    plt.plot(scaler_toolbox.inverse_transform(actual_values), label='Actual Values')
    plt.plot(denormalized_predictions, label='Predicted Values')
    plt.xlabel('Timestep')
    plt.ylabel('Value')
    plt.title('Comparison of Predicted and Actual Values')
    plt.legend()
    plt.show()
