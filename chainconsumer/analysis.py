import logging
import numpy as np
from scipy.integrate import simps
from scipy.interpolate import interp1d
from scipy.ndimage.filters import gaussian_filter
from chainconsumer.helpers import get_smoothed_bins, get_grid_bins, get_latex_table_frame
from chainconsumer.kde import MegKDE


class Analysis(object):
    def __init__(self, parent):
        self.parent = parent
        self._logger = logging.getLogger(__name__)

        self._summaries = {
            "max": self.get_parameter_summary_max,
            "mean": self.get_parameter_summary_mean,
            "cumulative": self.get_parameter_summary_cumulative
        }

    def get_latex_table(self, parameters=None, transpose=False, caption=None,
                        label="tab:model_params", hlines=True, blank_fill="--"):  # pragma: no cover
        """ Generates a LaTeX table from parameter summaries.

        Parameters
        ----------
        parameters : list[str], optional
            A list of what parameters to include in the table. By default, includes all parameters
        transpose : bool, optional
            Defaults to False, which gives each column as a parameter, each chain (framework)
            as a row. You can swap it so that you have a parameter each row and a framework
            each column by setting this to True
        caption : str, optional
            If you want to generate a caption for the table through Python, use this.
            Defaults to an empty string
        label : str, optional
            If you want to generate a label for the table through Python, use this.
            Defaults to an empty string
        hlines : bool, optional
            Inserts ``\\hline`` before and after the header, and at the end of table.
        blank_fill : str, optional
            If a framework does not have a particular parameter, will fill that cell of
            the table with this string.

        Returns
        -------
        str
            the LaTeX table.
        """
        if parameters is None:
            parameters = self.parent._all_parameters
        for name in self.parent._names:
            assert name is not None, \
                "Generating a LaTeX table requires all chains to have names." \
                " Ensure you have `name=` in your `add_chain` call"
        for p in parameters:
            assert isinstance(p, str), \
                "Generating a LaTeX table requires all parameters have labels"
        num_parameters = len(parameters)
        num_chains = len(self.parent._chains)
        fit_values = self.get_summary(squeeze=False)
        if label is None:
            label = ""
        if caption is None:
            caption = ""

        end_text = " \\\\ \n"
        if transpose:
            column_text = "c" * (num_chains + 1)
        else:
            column_text = "c" * (num_parameters + 1)

        center_text = ""
        hline_text = "\\hline\n"
        if hlines:
            center_text += hline_text + "\t\t"
        if transpose:
            center_text += " & ".join(["Parameter"] + self.parent._names) + end_text
            if hlines:
                center_text += "\t\t" + hline_text
            for p in parameters:
                arr = ["\t\t" + p]
                for chain_res in fit_values:
                    if p in chain_res:
                        arr.append(self.get_parameter_text(*chain_res[p], wrap=True))
                    else:
                        arr.append(blank_fill)
                center_text += " & ".join(arr) + end_text
        else:
            center_text += " & ".join(["Model"] + parameters) + end_text
            if hlines:
                center_text += "\t\t" + hline_text
            for name, chain_res in zip(self.parent._names, fit_values):
                arr = ["\t\t" + name]
                for p in parameters:
                    if p in chain_res:
                        arr.append(self.get_parameter_text(*chain_res[p], wrap=True))
                    else:
                        arr.append(blank_fill)
                center_text += " & ".join(arr) + end_text
        if hlines:
            center_text += "\t\t" + hline_text
        final_text = get_latex_table_frame(caption, label) % (column_text, center_text)

        return final_text

    def get_summary(self, squeeze=True, parameters=None):
        """  Gets a summary of the marginalised parameter distributions.

        Parameters
        ----------
        squeeze : bool, optional
            Squeeze the summaries. If you only have one chain, squeeze will not return
            a length one list, just the single summary. If this is false, you will
            get a length one list.
        parameters : list[str], optional
            A list of parameters which to generate summaries for.

        Returns
        -------
        list of dictionaries
            One entry per chain, parameter bounds stored in dictionary with parameter as key
        """
        find_parameters = parameters
        results = []
        for ind, (chain, parameters, weights, g) in enumerate(zip(self.parent._chains,
                                                                  self.parent._parameters,
                                                                  self.parent._weights,
                                                                  self.parent._grids)):
            res = {}
            for i, p in enumerate(parameters):
                if find_parameters is not None and p not in find_parameters:
                    continue
                summary = self._get_parameter_summary(chain[:, i], weights, p, ind, grid=g)
                res[p] = summary
            results.append(res)
        if squeeze and len(results) == 1:
            return results[0]
        return results

    def _get_parameter_summary(self, data, weights, parameter, chain_index, **kwargs):
        if not self.parent._configured:
            self.parent.configure()
        method = self._summaries[self.parent.config["statistics"][chain_index]]
        return method(data, weights, parameter, chain_index, **kwargs)

    def get_correlations(self, chain=0, parameters=None):
        """
        Takes a chain and returns the correlation between chain parameters.

        Parameters
        ----------
        chain : int|str, optional
            The chain index or name. Defaults to first chain.
        parameters : list[str], optional
            The list of parameters to compute correlations. Defaults to all parameters
            for the given chain.

        Returns
        -------
            tuple
                The first index giving a list of parameter names, the second index being the
                2D correlation matrix.
        """
        chain = self.parent._get_chain(chain)
        if parameters is None:
            parameters = self.parent._parameters[chain]

        indexes = [self.parent._parameters[chain].index(p) for p in parameters]
        data = self.parent._chains[chain][:, indexes]
        correlations = np.atleast_2d(np.corrcoef(data, rowvar=0))

        return parameters, correlations

    def get_covariance(self, chain=0, parameters=None):
        """
        Takes a chain and returns the covariance between chain parameters.

        Parameters
        ----------
        chain : int|str, optional
            The chain index or name. Defaults to first chain.
        parameters : list[str], optional
            The list of parameters to compute correlations. Defaults to all parameters
            for the given chain.

        Returns
        -------
            tuple
                The first index giving a list of parameter names, the second index being the
                2D covariance matrix.
        """
        chain = self.parent._get_chain(chain)
        if parameters is None:
            parameters = self.parent._parameters[chain]

        indexes = [self.parent._parameters[chain].index(p) for p in parameters]
        data = self.parent._chains[chain][:, indexes]
        correlations = np.atleast_2d(np.cov(data, aweights=self.parent._weights[chain], rowvar=False))

        return parameters, correlations

    def get_correlation_table(self, chain=0, parameters=None, caption="Parameter Correlations",
                              label="tab:parameter_correlations"):
        """
        Gets a LaTeX table of parameter correlations.

        Parameters
        ----------
        chain : int|str, optional
            The chain index or name. Defaults to first chain.
        parameters : list[str], optional
            The list of parameters to compute correlations. Defaults to all parameters
            for the given chain.
        caption : str, optional
            The LaTeX table caption.
        label : str, optional
            The LaTeX table label.

        Returns
        -------
            str
                The LaTeX table ready to go!
        """
        parameters, cor = self.get_correlations(chain=chain, parameters=parameters)
        return self._get_2d_latex_table(parameters, cor, caption, label)

    def get_covariance_table(self, chain=0, parameters=None, caption="Parameter Covariance",
                              label="tab:parameter_covariance"):
        """
        Gets a LaTeX table of parameter covariance.

        Parameters
        ----------
        chain : int|str, optional
            The chain index or name. Defaults to first chain.
        parameters : list[str], optional
            The list of parameters to compute correlations. Defaults to all parameters
            for the given chain.
        caption : str, optional
            The LaTeX table caption.
        label : str, optional
            The LaTeX table label.

        Returns
        -------
            str
                The LaTeX table ready to go!
        """
        parameters, cov = self.get_covariance(chain=chain, parameters=parameters)
        return self._get_2d_latex_table(parameters, cov, caption, label)

    def _get_smoothed_histogram(self, data, weights, chain_index, grid):
        smooth = self.parent.config["smooth"][chain_index]
        if grid:
            bins = get_grid_bins(data)
        else:
            bins = self.parent.config['bins'][chain_index]
            bins, smooth = get_smoothed_bins(smooth, bins, data, weights)

        hist, edges = np.histogram(data, bins=bins, normed=True, weights=weights)
        edge_centers = 0.5 * (edges[1:] + edges[:-1])
        xs = np.linspace(edge_centers[0], edge_centers[-1], 10000)

        if smooth:
            hist = gaussian_filter(hist, smooth, mode=self.parent._gauss_mode)
        kde = self.parent.config["kde"][chain_index]
        if kde:
            kde_xs = np.linspace(edge_centers[0], edge_centers[-1], max(200, int(bins.max())))
            ys = MegKDE(data, weights, factor=kde).evaluate(kde_xs)
            area = simps(ys, x=kde_xs)
            ys = ys / area
            ys = interp1d(kde_xs, ys, kind="linear")(xs)
        else:
            ys = interp1d(edge_centers, hist, kind="linear")(xs)
        cs = ys.cumsum()
        cs /= cs.max()
        return xs, ys, cs

    def _get_2d_latex_table(self, parameters, matrix, caption, label):
        latex_table = get_latex_table_frame(caption=caption, label=label)
        column_def = "c|%s" % ("c" * len(parameters))
        hline_text = "        \\hline\n"

        table = ""
        table += " & ".join([""] + parameters) + "\\\\ \n"
        table += hline_text
        max_len = max([len(s) for s in parameters])
        format_string = "        %%%ds" % max_len
        for p, row in zip(parameters, matrix):
            table += format_string % p
            for r in row:
                table += " & %5.2f" % r
            table += " \\\\ \n"
        table += hline_text
        return latex_table % (column_def, table)

    def get_parameter_text(self, lower, maximum, upper, wrap=False):
        """ Generates LaTeX appropriate text from marginalised parameter bounds.

        Parameters
        ----------
        lower : float
            The lower bound on the parameter
        maximum : float
            The value of the parameter with maximum probability
        upper : float
            The upper bound on the parameter
        wrap : bool
            Wrap output text in dollar signs for LaTeX

        Returns
        -------
        str
            The formatted text given the parameter bounds
        """
        if lower is None or upper is None:
            return ""
        upper_error = upper - maximum
        lower_error = maximum - lower
        if upper_error != 0 and lower_error != 0:
            resolution = min(np.floor(np.log10(np.abs(upper_error))),
                            np.floor(np.log10(np.abs(lower_error))))
        elif upper_error == 0 and lower_error != 0:
            resolution = np.floor(np.log10(np.abs(lower_error)))
        elif upper_error != 0 and lower_error == 0:
            resolution = np.floor(np.log10(np.abs(upper_error)))
        else:
            resolution = np.floor(np.log10(np.abs(maximum)))
        factor = 0
        fmt = "%0.1f"
        r = 1
        if np.abs(resolution) > 2:
            factor = -resolution
        if resolution == 2:
            fmt = "%0.0f"
            factor = -1
            r = 0
        if resolution == 1:
            fmt = "%0.0f"
        if resolution == -1:
            fmt = "%0.2f"
            r = 2
        elif resolution == -2:
            fmt = "%0.3f"
            r = 3
        upper_error *= 10 ** factor
        lower_error *= 10 ** factor
        maximum *= 10 ** factor
        upper_error = round(upper_error, r)
        lower_error = round(lower_error, r)
        maximum = round(maximum, r)
        if maximum == -0.0:
            maximum = 0.0
        if resolution == 2:
            upper_error *= 10 ** -factor
            lower_error *= 10 ** -factor
            maximum *= 10 ** -factor
            factor = 0
            fmt = "%0.0f"
        upper_error_text = fmt % upper_error
        lower_error_text = fmt % lower_error
        if upper_error_text == lower_error_text:
            text = r"%s\pm %s" % (fmt, "%s") % (maximum, lower_error_text)
        else:
            text = r"%s^{+%s}_{-%s}" % (fmt, "%s", "%s") % \
                   (maximum, upper_error_text, lower_error_text)
        if factor != 0:
            text = r"\left( %s \right) \times 10^{%d}" % (text, -factor)
        if wrap:
            text = "$%s$" % text
        return text

    def get_parameter_summary_mean(self, data, weights, parameter, chain_index, desired_area=0.6827, grid=False):
        xs, _, cs = self._get_smoothed_histogram(data, weights, chain_index, grid)
        vals = [0.5 - desired_area / 2, 0.5, 0.5 + desired_area / 2]
        bounds = interp1d(cs, xs)(vals)
        bounds[1] = 0.5 * (bounds[0] + bounds[2])
        return bounds

    def get_parameter_summary_cumulative(self, data, weights, parameter, chain_index, desired_area=0.6827, grid=False):
        xs, _, cs = self._get_smoothed_histogram(data, weights, chain_index, grid)
        vals = [0.5 - desired_area / 2, 0.5, 0.5 + desired_area / 2]
        bounds = interp1d(cs, xs)(vals)
        return bounds

    def get_parameter_summary_max(self, data, weights, parameter, chain_index, desired_area=0.6827, grid=False):
        xs, ys, cs = self._get_smoothed_histogram(data, weights, chain_index, grid)
        n_pad = 1000
        x_start = xs[0] * np.ones(n_pad)
        x_end = xs[-1] * np.ones(n_pad)
        y_start = np.linspace(0, ys[0], n_pad)
        y_end = np.linspace(ys[-1], 0, n_pad)
        xs = np.concatenate((x_start, xs, x_end))
        ys = np.concatenate((y_start, ys, y_end))
        cs = ys.cumsum()
        cs = cs / cs.max()
        startIndex = ys.argmax()
        maxVal = ys[startIndex]
        minVal = 0
        threshold = 0.001
        x1 = None
        x2 = None
        count = 0
        while x1 is None:
            mid = (maxVal + minVal) / 2.0
            count += 1
            try:
                if count > 50:
                    raise ValueError("Failed to converge")
                i1 = startIndex - np.where(ys[:startIndex][::-1] < mid)[0][0]
                i2 = startIndex + np.where(ys[startIndex:] < mid)[0][0]
                area = cs[i2] - cs[i1]
                deviation = np.abs(area - desired_area)
                if deviation < threshold:
                    x1 = xs[i1]
                    x2 = xs[i2]
                elif area < desired_area:
                    maxVal = mid
                elif area > desired_area:
                    minVal = mid
            except ValueError:
                self._logger.warning("Parameter %s is not constrained" % parameter)
                return [None, xs[startIndex], None]

        return [x1, xs[startIndex], x2]

