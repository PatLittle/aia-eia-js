<template>
  <div class="requirements">
    <div class="container-fluid">
      <div class="row">
        <h2 id="obligations">
          {{ $t("requirements.title", locale) }} {{ impactLevel }}
        </h2>
      </div>
      <div
        class="row"
        v-for="requirement in $t('requirements.elements', locale)"
        :key="requirement.title"
      >
        <h3>{{ requirement.title }}</h3>
        <list-item :text="requirement.elements[impactLevel - 1].text" />
      </div>
      <div class="row">
        <h3>{{ $t("otherRequirementsTitle", locale) }}</h3>
        <p>{{ $t("otherRequirements", locale) }}</p>
        <p>
          <a :href="$t('linkDirective', locale)" target="_blank">
            {{ $t("linkDirectiveText", locale) }}
          </a>
        </p>
        <p>{{ $t("contactAtipForPia", locale) }}</p>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import Vue from "vue";
import i18n from "@/plugins/i18n";
import Component from "vue-class-component";
import ListItem from "@/components/ListItem.vue";

@Component({
  props: ["locale"],
  components: {
    ListItem
  }
})
export default class Obligations extends Vue {
  get impactLevel(): number {
    const level = Number(this.$store.getters.calcScore[3]);
    return level >= 1 && level <= 4 ? level : 1;
  }
}
</script>
