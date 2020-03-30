import warnings

from numpy import nan

with warnings.catch_warnings():
    warnings.simplefilter("ignore")

    from rpy2 import robjects as rob
    from rpy2.robjects.packages import importr
    from rpy2.robjects import FloatVector
    from rpy2.robjects import StrVector
    from rpy2.robjects import Formula

    survival = importr('survival')
    survcomp = importr('survcomp')
    glmnet = importr('glmnet')

import numpy as np

def main():
    """
    DEBUG
    """
    isdead = [0, 1, 1, 1, 0, 1, 0, 0, 1, 0]
    nbdays = [24, 10, 25, 50, 14, 10 ,100, 10, 50, 10]
    values = [0, 1, 1, 0 , 1, 2, 0, 1, 0, 0]
    np.random.seed(2016)

    values_proba = np.random.random(10)
    pvalue_proba = coxph(values_proba, isdead, nbdays,
                         do_KM_plot=True,
                         dichotomize_afterward=True)
    print(pvalue_proba)

   # matrix = np.random.random((10, 2))

    isdead_test = np.random.randint(0, 1, 10)

    pvalue = coxph(values, isdead, nbdays, isfactor=True)
    print('pvalue:', pvalue)
    # surv = coxph(Mr, 1, nbdays, isdead)

    cindex = c_index(
        values,
        isdead,
        nbdays,
        values,
        isdead_test,
        nbdays)

    print('c index:', cindex)


def coxph(values,
          isdead,
          nbdays,
          do_KM_plot=False,
          png_path='./',
          dichotomize_afterward=False,
          fig_name='KM_plot.png',
          isfactor=False):
    """
    input:
        :values: array    values of activities
        :isdead: array <binary>    Event occured int boolean: 0/1
        :nbdays: array <int>
    return:
        pvalues from wald test
    """
    isdead = FloatVector(isdead)
    nbdays = FloatVector(nbdays)

    if isfactor:
        # values_str = 'factor({0})'.format(values_str)
        values = StrVector(values)
    else:
        values = FloatVector(values)

    cox = Formula('Surv(nbdays, isdead) ~ values')

    cox.environment['nbdays'] = nbdays
    cox.environment['isdead'] = isdead
    cox.environment['values'] = values

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = survival.coxph(cox)
    except Exception as e:
        warnings.warn('Cox-PH didnt fit return NaN: {0}'.format(e))
        return np.nan

    pvalue = rob.r.summary(res)[-5][2]
    # color = ['green', 'blue', 'red']
    pvalue_to_print = pvalue

    if do_KM_plot:
        if dichotomize_afterward:
            frame = rob.r('data.frame')
            predicted = np.array(rob.r.predict(res, frame(values=values)))
            new_values = predicted.copy()
            med = np.median(predicted)
            new_values[predicted >= med] = 0
            new_values[predicted < med] = 1
            new_values = FloatVector(new_values)
            pvalue_to_print = coxph(new_values, isdead, nbdays)

            cox.environment['values'] = new_values

        surv = survival.survfit(cox)
        rob.r.png("{0}/{1}.png".format(png_path, fig_name.replace('.png', '')))
        rob.r.plot(surv,
                   col=rob.r("2:8"),
                   xlab="Days",
                   ylab="Probablity of survival",
                   sub='pvalue: {0}'.format(pvalue_to_print),
                   lwd=3,
                   mark_time=True
            )

        rob.r("dev.off()")
        print("{0}/{1}.png saved!".format(png_path, fig_name.replace('.png', '')))

        del res, surv, cox

    return pvalue

def c_index(values,
            isdead,
            nbdays,
            values_test,
            isdead_test,
            nbdays_test,
            isfactor=False):
    """ """
    rob.r('set.seed(2016)')
    isdead = FloatVector(isdead)
    isdead_test = FloatVector(isdead_test)

    nbdays = FloatVector(nbdays)
    nbdays_test = FloatVector(nbdays_test)

    values = FloatVector(values)
    values_test = FloatVector(values_test)

    if isfactor:
        values = StrVector(values)
        values_test = StrVector(values_test)

    cox = Formula('Surv(nbdays, isdead) ~ values')

    cox.environment['nbdays'] = nbdays
    cox.environment['isdead'] = isdead
    cox.environment['values'] = values

    res = survival.coxph(cox)
    frame = rob.r('data.frame')
    predict = rob.r.predict(res, frame(values=values_test))
    concordance_index = rob.r('concordance.index')

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c_index = concordance_index(predict,
                                        nbdays_test,
                                        isdead_test,
            method='noether')
    except Exception as e:
        print("exception found for c index!: {0}".format(e))
        return nan

    del res, cox, frame

    return c_index[0][0]

def c_index_multiple(
        matrix,
        isdead,
        nbdays,
        matrix_test,
        isdead_test,
        nbdays_test,
        lambda_val=None):
    """
    """
    rob.r('set.seed(2016)')

    if matrix.shape[1] < 2:
        return np.nan

    nbdays[nbdays == 0] = 1
    nbdays_test[nbdays_test == 0] = 1

    isdead = FloatVector(isdead)
    isdead_test = FloatVector(isdead_test)

    nbdays = FloatVector(nbdays)
    nbdays_test = FloatVector(nbdays_test)

    matrix = convert_to_rmatrix(matrix)
    matrix_test = convert_to_rmatrix(matrix_test)

    surv = survival.Surv(nbdays, isdead)

    cv_glmnet = rob.r('cv.glmnet')
    glmnet = rob.r('glmnet')

    arg = {'lambda': lambda_val}

    if not lambda_val:
        cv_fit = cv_glmnet(matrix, surv, family='cox', alpha=0)
        arg = {'lambda': min(cv_fit[0])}

    fit = glmnet(matrix, surv, family='cox', alpha=0, **arg)

    predict = rob.r.predict(fit, matrix_test)
    concordance_index = rob.r('concordance.index')

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c_index = concordance_index(predict,
                                        nbdays_test,
                                        isdead_test,
                                        method='noether')
    except Exception as e:
        print("exception found for c index multiple!: {0}".format(e))
        return None

    return c_index[0][0]


def predict_with_coxph_glmnet(
        matrix,
        isdead,
        nbdays,
        matrix_test,
        alpha=0.5,
        lambda_val=None):
    """
    """
    rob.r('set.seed(2020)')

    if matrix.shape[1] < 2:
        return np.nan

    nbdays[nbdays == 0] = 1

    isdead = FloatVector(isdead)

    nbdays = FloatVector(nbdays)

    matrix = convert_to_rmatrix(matrix)
    matrix_test = convert_to_rmatrix(matrix_test)

    surv = survival.Surv(nbdays, isdead)

    cv_glmnet = rob.r('cv.glmnet')
    glmnet = rob.r('glmnet')

    arg = {'lambda': lambda_val}

    if not lambda_val:
        cv_fit = cv_glmnet(matrix, surv, family='cox',
                           alpha=alpha)
        arg = {'lambda': min(cv_fit[0])}

    fit = glmnet(matrix, surv, family='cox', alpha=0, **arg)

    return np.asarray(rob.r.predict(fit, matrix_test)).T[0]


def convert_to_rmatrix(data):
    """ """
    shape = data.shape
    return rob.r.t(
        rob.r.matrix(
            rob.FloatVector(
                list(np.resize(data, shape[0] * shape[1]))),
            nrow=shape[1], ncol=shape[0])
    )

def surv_mean(isdead,nbdays):
    """ """
    isdead = FloatVector(isdead)
    nbdays = FloatVector(nbdays)

    surv = rob.r.summary(survival.Surv(nbdays, isdead))

    return float(surv[3].split(':')[1])

def surv_median(isdead,nbdays):
    """ """
    isdead = FloatVector(isdead)
    nbdays = FloatVector(nbdays)

    surv = rob.r.summary(survival.Surv(nbdays, isdead))

    return float(surv[2].split(':')[1])

if __name__ == "__main__":
    main()
