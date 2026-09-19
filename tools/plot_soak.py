"""plots a soak run from the verdict log: temperature, crystal rate, rate against temperature, and the cross-check"""

import datetime
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

logPath = sys.argv[1]
outPath = sys.argv[2]
cleanFrom = sys.argv[3]
limitSeconds = 0.050
torontoOffset = datetime.timedelta(hours=-4)

surface = "#fcfcfb"
inkPrimary = "#0b0b0b"
inkSecondary = "#52514e"
gridInk = "#e4e3df"
seriesBlue = "#2a78d6"

rows = [json.loads(row) for row in open(logPath, encoding="utf-8") if row.strip()]
clean = [row for row in rows if row["time"] >= cleanFrom and row["state"] == "LOCKED"]


def localTime(stamp):
    return datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ") + torontoOffset


times = []
temperatures = []
rates = []
crossCheck = []
for row in clean:
    detail = row["detail"]
    if detail.get("boardTemperatureC") is None or detail.get("frequencyPpm") is None:
        continue
    times.append(localTime(row["time"]))
    temperatures.append(detail["boardTemperatureC"])
    rates.append(detail["frequencyPpm"])
    crossCheck.append(detail.get("satelliteVersusServersWorst", 0.0) * 1000.0)

count = len(times)
meanTemperature = sum(temperatures) / count
meanRate = sum(rates) / count
covariance = sum((temperatures[i] - meanTemperature) * (rates[i] - meanRate) for i in range(count))
spreadTemperature = sum((value - meanTemperature) ** 2 for value in temperatures)
spreadRate = sum((value - meanRate) ** 2 for value in rates)
slope = covariance / spreadTemperature
correlation = covariance / (spreadTemperature * spreadRate) ** 0.5
intercept = meanRate - slope * meanTemperature

plt.rcParams.update({
    "font.size": 10,
    "axes.edgecolor": gridInk,
    "axes.labelcolor": inkSecondary,
    "xtick.color": inkSecondary,
    "ytick.color": inkSecondary,
    "text.color": inkPrimary,
})

figure, axes = plt.subplots(2, 2, figsize=(12, 8.5), facecolor=surface)
figure.suptitle("24 hour soak, GPS disciplined Raspberry Pi 5, 2026-09-17 to 18, Toronto time",
                fontsize=13, color=inkPrimary, x=0.02, ha="left")

timeFormat = mdates.DateFormatter("%H:%M")


def styleAxis(axis, title, yLabel):
    axis.set_facecolor(surface)
    axis.set_title(title, loc="left", fontsize=11, color=inkPrimary)
    axis.set_ylabel(yLabel)
    axis.grid(True, color=gridInk, linewidth=0.8)
    axis.set_axisbelow(True)
    for side in ["top", "right"]:
        axis.spines[side].set_visible(False)


def hourlyBands(values):
    buckets = {}
    order = []
    index = 0
    while index < count:
        hour = times[index].replace(minute=30, second=0)
        if hour not in buckets:
            buckets[hour] = []
            order.append(hour)
        buckets[hour].append(values[index])
        index += 1
    means = [sum(buckets[hour]) / len(buckets[hour]) for hour in order]
    lows = [min(buckets[hour]) for hour in order]
    highs = [max(buckets[hour]) for hour in order]
    return order, means, lows, highs


hours, temperatureMeans, temperatureLows, temperatureHighs = hourlyBands(temperatures)
styleAxis(axes[0][0], "Board temperature, hourly mean, band is the hour's range", "degrees C")
axes[0][0].fill_between(hours, temperatureLows, temperatureHighs, color=seriesBlue, alpha=0.16, linewidth=0)
axes[0][0].plot(hours, temperatureMeans, color=seriesBlue, linewidth=2)
axes[0][0].xaxis.set_major_formatter(timeFormat)

hours, rateMeans, rateLows, rateHighs = hourlyBands(rates)
styleAxis(axes[0][1], "Crystal rate error as chrony corrects it, hourly mean and range", "ppm fast")
axes[0][1].fill_between(hours, rateLows, rateHighs, color=seriesBlue, alpha=0.16, linewidth=0)
axes[0][1].plot(hours, rateMeans, color=seriesBlue, linewidth=2)
axes[0][1].xaxis.set_major_formatter(timeFormat)

styleAxis(axes[1][0], "Rate error against temperature", "ppm fast")
axes[1][0].scatter(temperatures, rates, s=36, color=seriesBlue, edgecolors=surface, linewidths=1.5, zorder=3)
fitX = [min(temperatures), max(temperatures)]
fitY = [intercept + slope * value for value in fitX]
axes[1][0].plot(fitX, fitY, color=inkSecondary, linewidth=1.5, linestyle="--", zorder=2)
axes[1][0].set_xlabel("board temperature, degrees C")
axes[1][0].text(0.02, 0.04, "%.3f ppm per degree, r = %.2f, n = %d" % (slope, correlation, count),
                transform=axes[1][0].transAxes, ha="left", va="bottom", color=inkSecondary,
                bbox={"facecolor": surface, "edgecolor": "none", "pad": 3})

styleAxis(axes[1][1], "GPS against the internet servers, worst gap per sample", "milliseconds")
axes[1][1].plot(times, crossCheck, color=seriesBlue, linewidth=2)
axes[1][1].axhline(limitSeconds * 1000.0, color=inkSecondary, linewidth=1.5, linestyle="--")
axes[1][1].text(times[0], limitSeconds * 1000.0 + 1.0, "UNTRUSTED above 50 ms", color=inkSecondary, va="bottom")
axes[1][1].set_ylim(0, limitSeconds * 1000.0 * 1.2)
axes[1][1].xaxis.set_major_formatter(timeFormat)

figure.tight_layout(rect=[0, 0, 1, 0.95])
figure.savefig(outPath, dpi=130, facecolor=surface)
print("wrote %s from %d samples, slope %.4f ppm per C, r %.3f" % (outPath, count, slope, correlation))
