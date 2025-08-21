import csv
import ast

def main():
    # Specify the file path
    file_path = "surgery_times_8weeks.csv"
    output_path = "surgery_times_8weeks_trace.dat"
    output_path_transposed = "surgery_times_8weeks_trace_transposed.dat"
    day = -1
    trace_length_minutes = 8 * 7 * 24 * 60;
    operating_room_traces = {'OR1': [0] * trace_length_minutes,
                             'OR2': [0] * trace_length_minutes,
                             'OR3': [0] * trace_length_minutes,
                             'OR4': [0] * trace_length_minutes,
                             'OR5': [0] * trace_length_minutes,
                             'OR6': [0] * trace_length_minutes,
                             'OR7': [0] * trace_length_minutes,
                             'OR8': [0] * trace_length_minutes,
                             'OR9': [0] * trace_length_minutes,
                             'OR10': [0] * trace_length_minutes}
    try:
        # Open the CSV file
        with open(file_path, newline='') as csvfile:
            # Create a CSV reader object
            reader = csv.reader(csvfile)
            
            # Iterate over each row in the CSV file
            for row in reader:
                # Account for the days of the week
                if row != [] and row[0].startswith('DAY'):
                    day += 1
                    print("Processing day: " + str(day))
                
                # Process a row related to an OR surgeries
                if row != [] and row[0].startswith('OR'):
                    operating_room = row[0]
                    print("Operating room: " + operating_room)
                    del row[0]
                    for surgery_time in row:                      
                        surgery_time = ast.literal_eval(surgery_time)
                        (ini_time, end_time) = (surgery_time[0], surgery_time[1])
                        ini_time_min_in_trace = int(ini_time * 60) + (day * 24 * 60)
                        end_time_min_in_trace = int(end_time * 60) + (day * 24 * 60)
                        operating_room_traces[operating_room][ini_time_min_in_trace:end_time_min_in_trace] = [1] * (end_time_min_in_trace - ini_time_min_in_trace)
                        print("Operating room " + operating_room + " occupied from " + str(ini_time_min_in_trace) + " to " + str(end_time_min_in_trace))
        
        parallel_surgeries = [0] * trace_length_minutes
        for i in range(trace_length_minutes):
            for k in operating_room_traces.keys():
                parallel_surgeries[i] += operating_room_traces[k][i]
        operating_room_traces['ALL'] = parallel_surgeries
        
        with open(output_path, "w") as file:
            for key, value in operating_room_traces.items():
                file.write(key + ': ' + ' '.join(map(str, value)) + '\n')
                
        # Read the original file and transpose its contents
        with open(output_path, "r") as file:
            lines = file.readlines()

            # Transpose the data
            transposed_data = zip(*(line.strip().split(': ')[1].split() for line in lines))
            
            # Write the transposed data to the new file
            with open(output_path_transposed, "w") as file:
                for row in transposed_data:
                    file.write(' '.join(row) + '\n')

    except FileNotFoundError:
        print(f"File '{file_path}' not found.")

if __name__ == "__main__":
    main()
