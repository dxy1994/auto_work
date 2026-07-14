import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAllWebsites, getCategories } from '../api'

export const useWebsiteStore = defineStore('website', () => {
  const allWebsites = ref([])
  const categories = ref([])

  async function fetchAll() {
    allWebsites.value = await getAllWebsites()
  }

  async function fetchCategories() {
    categories.value = await getCategories()
  }

  return { allWebsites, categories, fetchAll, fetchCategories }
})
