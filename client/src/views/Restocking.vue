<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="successMessage" class="success-banner">{{ successMessage }}</div>
      <div v-if="submitError" class="error">{{ submitError }}</div>

      <div v-if="candidates.length === 0" class="empty-state">
        {{ t('restocking.noCandidates') }}
      </div>
      <template v-else>
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
          </div>
          <div class="budget-controls">
            <input
              type="range"
              min="0"
              :max="maxBudget"
              step="100"
              v-model.number="budget"
              class="budget-slider"
            />
            <div class="budget-readout">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
          </div>

          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-label">{{ t('restocking.totalCost') }}</div>
              <div class="stat-value">{{ currencySymbol }}{{ totalCost.toLocaleString() }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
              <div class="stat-value">{{ currencySymbol }}{{ remainingBudget.toLocaleString() }}</div>
            </div>
          </div>

          <button
            class="place-order-btn"
            :disabled="selectedItems.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div class="card">
          <div class="card-header">
            <h3 class="card-title">{{ t('restocking.title') }}</h3>
          </div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.name') }}</th>
                  <th>{{ t('restocking.table.currentDemand') }}</th>
                  <th>{{ t('restocking.table.forecastedDemand') }}</th>
                  <th>{{ t('restocking.table.shortfall') }}</th>
                  <th>{{ t('restocking.table.recommendedQty') }}</th>
                  <th>{{ t('restocking.table.unitCost') }}</th>
                  <th>{{ t('restocking.table.lineTotal') }}</th>
                  <th>{{ t('demand.table.trend') }}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="candidate in candidates"
                  :key="candidate.sku"
                  :class="{ 'excluded-row': !isIncluded(candidate.sku) }"
                >
                  <td><strong>{{ candidate.sku }}</strong></td>
                  <td>{{ candidate.name }}</td>
                  <td>{{ candidate.current_demand }}</td>
                  <td>{{ candidate.forecasted_demand }}</td>
                  <td>{{ candidate.shortfall }}</td>
                  <td>{{ candidate.recommended_quantity }}</td>
                  <td>{{ currencySymbol }}{{ candidate.unit_cost.toLocaleString() }}</td>
                  <td>{{ currencySymbol }}{{ candidate.line_total.toLocaleString() }}</td>
                  <td>
                    <span :class="['badge', candidate.trend]">
                      {{ t(`trends.${candidate.trend}`) }}
                    </span>
                  </td>
                  <td>
                    <span :class="['badge', isIncluded(candidate.sku) ? 'success' : 'danger']">
                      {{ isIncluded(candidate.sku) ? t('restocking.included') : t('restocking.excluded') }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const loading = ref(true)
    const error = ref(null)
    const candidates = ref([])
    const budget = ref(0)
    const submitting = ref(false)
    const successMessage = ref(null)
    const submitError = ref(null)

    const maxBudget = computed(() => {
      return candidates.value.reduce((sum, c) => sum + c.line_total, 0)
    })

    // Greedy selection: walk candidates in shortfall-desc order (already sorted by backend),
    // include any candidate that fits in the remaining budget, but keep scanning past ones
    // that don't fit so lower-priority/cheaper items further down can still be included.
    const selectedItems = computed(() => {
      const selected = []
      let runningTotal = 0
      for (const candidate of candidates.value) {
        if (runningTotal + candidate.line_total <= budget.value) {
          selected.push(candidate)
          runningTotal += candidate.line_total
        }
      }
      return selected
    })

    const selectedSkus = computed(() => new Set(selectedItems.value.map(c => c.sku)))
    const isIncluded = (sku) => selectedSkus.value.has(sku)

    const totalCost = computed(() => {
      return selectedItems.value.reduce((sum, c) => sum + c.line_total, 0)
    })

    const remainingBudget = computed(() => budget.value - totalCost.value)

    const formatDate = (dateString) => {
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return new Date(dateString).toLocaleDateString(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    const loadCandidates = async () => {
      try {
        loading.value = true
        error.value = null
        candidates.value = await api.getRestockRecommendations()
        budget.value = Math.round(maxBudget.value / 2)
      } catch (err) {
        error.value = 'Failed to load restocking recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      submitting.value = true
      successMessage.value = null
      submitError.value = null
      try {
        const result = await api.submitRestockOrder({
          budget: budget.value,
          items: selectedItems.value.map(c => ({
            sku: c.sku,
            name: c.name,
            quantity: c.recommended_quantity,
            unit_price: c.unit_cost
          }))
        })
        successMessage.value = t('restocking.successMessage', {
          orderNumber: result.order_number,
          expectedDelivery: formatDate(result.expected_delivery)
        })
      } catch (err) {
        submitError.value = t('restocking.errorMessage', { error: err.message })
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadCandidates)

    return {
      t,
      loading,
      error,
      candidates,
      budget,
      maxBudget,
      selectedItems,
      isIncluded,
      totalCost,
      remainingBudget,
      submitting,
      successMessage,
      submitError,
      placeOrder,
      currencySymbol
    }
  }
}
</script>

<style scoped>
.budget-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0 1.5rem 1.5rem;
}

.budget-slider {
  flex: 1;
}

.budget-readout {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
  min-width: 100px;
  text-align: right;
}

.place-order-btn {
  margin: 0 1.5rem 1.5rem;
  padding: 0.75rem 1.5rem;
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.excluded-row {
  opacity: 0.5;
}

.success-banner {
  background: #d1fae5;
  color: #059669;
  border: 1px solid #a7f3d0;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  font-weight: 500;
}

.empty-state {
  color: #64748b;
  padding: 2rem;
  text-align: center;
}
</style>
