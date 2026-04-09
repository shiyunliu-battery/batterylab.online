# Data acquisition

- Section: Introductory topics about battery cell testing
- Pages: 9-10
- Source PDF: Test methods for battery understanding_v3_0.pdf

Data acquisition
The results of the test methods have to be stored. Different methods exist.
Fixed interval
A common way is to store all measurement parameters with a fixed sampling rate like every
second. This method is easy to implement and easy to plot since no time dependent X-axis is
needed. Also, battery models for BMS systems, often prefer data with a fixed time step. The
method has two inconveniences. It leads to a high amount of data, since to cover the dynamic
behaviour of measurement signals a tiny time interval has to be taken. In periods of little change in
signal, still a lot of data is captured. For transient and highly dynamic signals a short time step (like
1 s) can still be too slow to capture the complete dynamics.
Event-based
In event-based datalogging, data is stored when a threshold in value change for a given parameter
is surpassed. This can be every 20 mV change for the voltage sensor and every 100 mA change for
the current sensor. Most battery test machines accept C-rate as criterion, like 0,01 C change. The
advantage is that all phenomena are captured with the resolution that you give, up to the fastest
sample rate of the test machine, e.g. every 1 ms. If no points are captured, then the signals are
stable within the required resolution. A disadvantage is that for plotting the data, the time axis has
to be taken into account. For battery modelling, the data may need a resampling to fixed time
interval.
Combination
A combination of both methods is the usual way. A slow time interval is taken, like 1 min,
combined with event-based data acquisition. For graphs this can be nicer since in long periods with
hardly a change, still some data points become visible. Also, if the resolution was incidentally
chosen too coarsely, then still some data is captured.
Example
In Figure 1 the difference becomes clearly visible for a 10 s discharge pulse. In A the data is
captured every second: most data points lie away from the pulse. In B the data is captured event-
based with as criteria: 1 mV for the voltage and 0,01 C for the current. Most data is around the
pulse. The fact that data exists before the pulse is due to the additional fixed time interval of 1 min
(the combined method). In A the 10 s pulse is captured in 11 points, whereas in B 114 points are
captured: the voltage slopes are very well visible.
9

Test methods for improved battery cell understanding Introductory topics about battery cell testing
A B
Figure 1: data acquisition via fixed interval versus event-based capturing. In A every second the
voltage is sampled. In B data is sampled via the combined method that uses mainly criteria on the
change in parameter values.
The sudden drop in voltage at the pulse onset is less deep (180 mV) in B than in A (240 mV) since it
is quicker captured: the used test machine can store every 1 ms a data point, making it 1000 times
quicker than in A. To determine the ohmic resistance of the cell, this may be advantageous. From A
the ohmic resistance is 36 mΩ and from B it is 28 mΩ. The used resolution in B may be over-precise
and can be diminished: even using 5 mV change would have let to a more precise pulse shape than
in A. In the shown time frame, in A 250 points are captured and in B 440. Capturing data over a
longer time, containing rest periods, will favour the combined method for data storage efficiency.
Air flow and controlled temperature
[eCAIMAN, AIT (H.Popp)]
When conducting tests on batteries, often several ambient temperatures are of interest, e.g. to
determine low temperature performance or to gain temperature dependent data for modelling.
Also in standards many temperatures are prescribed. Hence, often temperature chambers are used
to fulfil this requirement. Normally circulation of air is needed to pass it over the coolers and
heating elements. For the test equipment this usually means a forced convection rather than a
natural convection which might be the desired one. Especially with forced convection in
temperature chambers fan speed, shadowing effects and position in the chamber can lead to both
different temperatures as well as dissimilar air flow rates. This can lead to following differences in
heat transfer2:
• natural convection: α = 4 … 15 W/(m²∙K)
• forced convection: α = 10 … 100 W/(m²∙K).
Despite having an overlapping region, these values differ significantly and may lead to different
results especially during thermal characterization. Additionally, the value for the climatic chamber
is an average value, local values can differ. Figure 2 shows a distribution of temperature sensors
within a climatic chamber during calibration and Table 1 shows the according temperatures. The
ambient temperature value set is 0°C and the mean deviation over all sensors is 0. It can be seen
2 M. Rudolph et. al, Batteries Conference, Nice, France, 2014
10