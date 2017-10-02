# -*- coding: utf-8 -*-
import pandas as pd
import logging
import queue
from threading import Thread

from mosyco.plotter import Plotter
from mosyco.inspector import Inspector
from mosyco.reader import Reader
import mosyco.parser

log = logging.getLogger(__package__)

# ==============================================================================
class Mosyco():
    """Represents an instance of the Model-System-Controller Prototype.

    The Mosyco architecture combines Reader and Inspector to simulate the live
    observation of a running system.

    Attributes:
        args: command line arguments
        reader: mosyco.Reader instance
        inspector: mosyco.Inspector instance
        plotter: mosyco.Plotter instance
    """

    def __init__(self, args):
        """Create a new Mosyco instance.

        Args:
            args: The command line arguments from mosyco.parser
        """
        self.args = args
        self.queue = queue.Queue()
        self.reader = Reader(args.systems, self.queue)
        self.inspector = Inspector(self.reader.df.index,
                                    self.reader.df[args.models], args,
                                    self.queue)
        if self.args.gui:
            self.plotter = Plotter(self)
        self.deviation_count = 0

    def run(self):
        """Start and run the Mosyco system."""
        if self.args.gui:
            self.plotter.show_plot()
        else:
            self.reader.start()
            for res in self.loop():
                log.debug(f'Ran through iteration. res: {res}')
                pass

    def loop(self):
        for t in self.inspector.receive_actual_value():
            assert len(self.args.systems) == len(t[1:])
            values = t._asdict()
            date = values.pop('Index')

            for system_name, val in values.items():
                (exceeds_threshold, _) = self.inspector.eval_actual(date, system_name)
                # TODO: how to output threshold deviations
                log.debug(f'Date: {date.date()} ' + \
                    f'- Model-Actual deviation for system: {system_name}')

            next_year = date.year + 1

            # at the end of each period, create a forecast for the following
            # TODO: allow flexible period as argument
            if date.month == 12 and date.day == 31:

                log.debug(f'Current date: {date.date()}')

                period = pd.Period(next_year)
                log.info(f'Generating forecast for {period}...')

                # generate the new forecast in separate thread
                self.current_fc_thread = Thread(target=self.inspector.predict,
                                                args=(period, self.args.systems),
                                                daemon=True)
                self.current_fc_thread.start()

            # pass data through to plotting engine
            yield (date, values)


# ==============================================================================

# read command line arguments & set log level
args = mosyco.parser.parse_arguments()
log.setLevel(args.loglevel)

log.info('Starting mosyco...')
log.debug('running in DEBUG Mode')

# Run Mosyco
app = Mosyco(args)
app.run()

log.debug(f'Total: {app.deviation_count} model-actual deviations detected.')
