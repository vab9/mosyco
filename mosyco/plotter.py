# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.figure import Figure

from PyQt5 import QtCore, QtWidgets

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
import multiprocessing as mp


class Plotter(QtWidgets.QApplication):
    """The Plotter is responsible for animating the Mosyco data.

    Attributes:
        inspector: Reference to the Inspector object
        reader: Reference to the Reader object
        plotting_queue: Queue used for communicating with Inspector
    """
    def __init__(self, args, reader, inspector, plotting_queue):
        super().__init__([__package__])
        self.args = args
        # there is only one model & system in GUI mode
        self.system_name = args.systems[0]
        self.model_name = args.models[0]
        self.reader_thread = reader
        self.inspector = inspector
        self.plotting_queue = plotting_queue
        self.df = inspector.df.copy()

        # TODO: get this from somewhere or leave as default
        # thi needs to be half the period b/c we need to divide it later
        # and relativedeltas can not always be divided but always multiplied
        self.half_period_length = relativedelta(months=6)
        self.deviation_count = 0
        self.artists = []
        self.paused = False
        self.prepare_plot()


    def run(self):
        # Todo: Daemon?!
        self.process = mp.Process(target=self._run_mosyco, daemon=True)
        self.process.start()
        # start gui
        self.main_widget.show()
        self.exec_()


    def _run_mosyco(self):
        self.reader_thread.start()
        self.inspector.start()



    def prepare_plot(self):
        """Prepare drawable objects for the animation."""

        plt.style.use('seaborn')
        self.df[self.system_name] = np.nan
        self.inspector.forecast['yhat'] = np.nan

        self.fig = Figure()
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)


        self.ax1.set_title('Detailed System View')
        self.ax2.set_title('System Overview')

        self.ax1.set_ylabel('Units')
        self.ax2.set_ylabel('Units')

        # TODO: better way to initialize line plots than list comprehension ?!

        # actual system line
        (self.ac_line, ) = self.ax1.plot(self.df.index, [0
                for i in range(len(self.df))], c='blue',
                ls='solid', lw=0.5)

        # actual resampled
        (self.acr_line, ) = self.ax2.plot(self.df.index, [0
                for i in range(len(self.df))], c='blue',
                ls='solid', lw=0.7)

        rs = self.df[self.model_name].resample('W').mean()

        # model resampled
        (self.m_line, ) = self.ax2.plot(
            rs.index,
            rs.values,
            c='green',
            ls='solid',
            lw=0.7,
            alpha=0.7,
            )

        # add lines to artist list
        self.artists.extend([self.ac_line, self.acr_line])

        # TODO: set lim automatically
        self.ax1.set_ylim(900, 1200)
        self.ax2.set_ylim(900, 1200)

        self.ax1.set_autoscaley_on(True)
        self.ax2.set_autoscaley_on(True)

        # prepare initial limits for the x-axes
        start_date = self.df.index[0]
        self.ax1.set_xlim(start_date, start_date
                          + self.half_period_length * 2)
        self.ax2.set_xlim(start_date, start_date
                          + self.half_period_length * 4)

        # add the legend
        self.ax1.legend([self.ac_line], ['Live System'])
        self.ax2.legend([self.acr_line, self.m_line],
                        ['System Weekly Mean', 'Model Weekly Mean'])

        # rotate tick labels for all subplots
        for ax in self.fig.axes:
            # matplotlib.pyplot.sca(ax)
            # plt.xticks(rotation=30)
            for label in ax.get_xticklabels():
                label.set_rotation(30)


        # tight_layout call should be at the end of this function
        self.fig.set_tight_layout(True)
        # self.fig.tight_layout(rect=[0, 0.03, 1, 0.95])

        # prepare the canvas
        self.prepare_canvas()

        # setup animation
        self.ani = animation.FuncAnimation(
            fig=self.fig,
            func=self.update,
            frames=self.get_data,
            interval=40,
            blit=False,
            )


    def prepare_canvas(self):
        """Prepare the Backend Canvas for drawing on it."""
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                    QtWidgets.QSizePolicy.Expanding)

        self.canvas.updateGeometry()

        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.main_widget.setWindowTitle('Model-/System-Controller '
            + 'Architecture Prototype')

        layout = QtWidgets.QVBoxLayout(self.main_widget)
        layout.addWidget(self.canvas)

        self.canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.canvas.setFocus()

        def keypress(self, e):
            if e.key == 'escape':
                self.closeAllWindows()
            elif e.key == ' ':
                # pause / unpause
                self.paused = not self.paused

        self.canvas.mpl_connect('key_press_event', keypress)


    def get_data(self):
        """Receive data from the inspector."""
        while self.paused:
            yield None

        try:
            yield self.plotting_queue.get_nowait()
        except Exception:
            # --> queue.Empty exception
            yield None

    def update(self, obj):
        """Determine what object was received and update plot accordingly."""
        if obj is None:
            return self.artists
        elif isinstance(obj, pd.DataFrame):
            return self.plot_forecast(obj)
        else:
            return self.plot_actual(obj)

    def plot_actual(self, row):
        """This function updates various plot elements.

        It is called in regular interval during the animation loop and is
        responsible for redrawing the lines and axes."""

        date = row['Index']

        # add row to df
        self.df.loc[row['Index'], self.system_name] = row[self.system_name]


        # resampled plot
        # TODO: necessary to resample the whole dataframe? or maybe just a window
        resampled = self.df[self.system_name].resample('W').mean()
        self.acr_line.set_data(resampled.index, resampled.values)

        # detailed plot
        self.ac_line.set_ydata(self.df[self.system_name])

        # get current upper bound of date axis
        ax1_right_lim = matplotlib.dates.num2date(self.ax1.get_xlim()[1])
        ax2_right_lim = matplotlib.dates.num2date(self.ax2.get_xlim()[1])

        # calculate center and remove timezone information for comparison
        ax1_center = ax1_right_lim - self.half_period_length
        ax2_center = ax2_right_lim - self.half_period_length * 2
        ax1_center = ax1_center.replace(tzinfo=None)
        ax2_center = ax2_center.replace(tzinfo=None)

        # set the new x_axis limits
        if date > ax1_center:
            self.ax1.set_xlim(date - self.half_period_length, date
                              + self.half_period_length)
        if date > ax2_center:
            self.ax2.set_xlim(date - self.half_period_length * 2, date
                              + self.half_period_length * 2)


        # adjust y-axis
        self.ax1.relim()
        self.ax2.relim()
        self.ax1.autoscale_view(tight=None, scalex=False, scaley=True)
        self.ax2.autoscale_view(tight=None, scalex=False, scaley=True)

        # return all artists that need to be redrawn
        return self.artists



    def plot_forecast(self, fc):
        """Draw a new forecast. Called whenever a new one is available."""

        # resample values for smoother plot
        rs_fc = fc.resample('W').mean()
        # TODO: necessary to resample whole df?
        # rs_m = self.df[self.model_name].resample('W').mean()
        rs_m = self.df.loc[fc.index, self.model_name].resample('W').mean()

        # We cannot update a PolyCollection so we need to delete the old
        # uncertainty corridor and warning patches and draw a new one.
        # try:
        #     self.ci.remove()
        #     self.dev_warn_below.remove()
        #     self.dev_warn_above.remove()
        # except AttributeError:
        #     pass

        # draw forecast confidence interval
        self.ci = self.ax2.fill_between(
            rs_fc.index,
            rs_fc['yhat_lower'],
            rs_fc['yhat_upper'],
            alpha=0.2,
            color='orange',
            linestyle=':',
            )

        # draw deviation between forecast and model
        # below
        self.dev_warn_below = self.ax2.fill_between(
            rs_fc.index,
            rs_fc['yhat_lower'],
            rs_m.values,
            where=rs_m.values < rs_fc['yhat_lower'],
            interpolate=True,
            alpha=0.3,
            color='red',
            linestyle=':',
            )

        # above
        self.dev_warn_above = self.ax2.fill_between(
            rs_fc.index,
            rs_fc['yhat_upper'],
            rs_m.values,
            where=rs_m.values > rs_fc['yhat_upper'],
            interpolate=True,
            alpha=0.3,
            color='red',
            linestyle=':',
            )

        try:
            self.fc_line.set_data(rs_fc.index, rs_fc['yhat'])
        except AttributeError:
            (self.fc_line, ) = self.ax2.plot(
                rs_fc.index,
                rs_fc['yhat'],
                c='black',
                ls='dashed',
                lw=0.7,
                alpha=0.4,
                )
            self.artists.append(self.fc_line)

           # update legend
            self.ax2.get_legend().remove()
            self.ax2.legend([self.ac_line, self.m_line, (self.fc_line,
                            self.ci), (self.dev_warn_above,
                            self.dev_warn_below)], ['Live System',
                            'System Model', 'Forecast \u00B1 CI',
                            'Model-Forecast Deviation'])

        return self.artists
